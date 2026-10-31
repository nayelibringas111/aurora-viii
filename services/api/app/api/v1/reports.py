"""M09 Reportes: ficha de proyecto, resumen de arquitectura, historial y comparación. CSV/PDF según permisos."""
import csv
import io
from xml.sax.saxutils import escape
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.common import iso, parse_uuid
from app.core.auth import get_current_user
from app.core.db import get_db
from app.core.permissions import Perm, authorize
from app.models import Architecture, Dataset, ModelVersion, Project, TrainingJob, TrainingMetric, User
from app.modules.audit import record
from app.modules.jobs import STATUS_LABELS

router = APIRouter(tags=["reports"])


def _history(db: Session, p: Project) -> list[dict]:
    rows = db.execute(select(TrainingJob, Architecture, Dataset.name)
                      .join(Architecture, Architecture.id == TrainingJob.architecture_id)
                      .join(Dataset, Dataset.id == TrainingJob.dataset_id)
                      .where(TrainingJob.project_id == p.id).order_by(TrainingJob.created_at.desc())).all()
    out = []
    for j, a, dn in rows:
        ev = j.result_json.get("evaluation", {})
        out.append({"job_id": str(j.id), "fecha": iso(j.created_at), "arquitectura": f"{a.name} v{a.version}",
                    "familia": a.family, "dataset": dn, "estado": STATUS_LABELS[j.status], "epocas": j.current_epoch,
                    "epocas_totales": j.total_epochs, "optimizador": j.params_json.get("optimizer"),
                    "learning_rate": j.params_json.get("learning_rate"), "batch_size": j.params_json.get("batch_size"),
                    "duracion_s": round((j.ended_at - j.started_at).total_seconds(), 1) if j.ended_at and j.started_at else None,
                    "test_loss": ev.get("loss"), "test_accuracy": ev.get("accuracy"),
                    "modelo_version": j.result_json.get("model_version")})
    return out


def _report(db: Session, p: Project) -> dict:
    archs = db.scalars(select(Architecture).where(Architecture.project_id == p.id).order_by(Architecture.created_at)).all()
    models = db.scalars(select(ModelVersion).where(ModelVersion.project_id == p.id).order_by(ModelVersion.version)).all()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": {"name": p.name, "description": p.description, "problem": p.problem, "tags": p.tags,
                    "status": p.status, "created_at": iso(p.created_at)},
        "architectures": [{"name": a.name, "version": a.version, "family": a.family, "justification": a.justification,
                           "total_params": a.summary_json.get("total_params"),
                           "layers": [f"{l['type']}{'(' + str(l.get('units') or l.get('filters') or '') + ')' if (l.get('units') or l.get('filters')) else ''} → {l['output_shape']}"
                                      for l in a.summary_json.get("layers", [])]} for a in archs],
        "history": _history(db, p),
        "models": [{"version": m.version, "status": m.status, "checksum": m.checksum[:16], "metrics": m.metrics_json}
                   for m in models],
    }


@router.get("/projects/{project_id}/report")
def project_report(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = authorize(db, parse_uuid(project_id, "proyecto"), user, Perm.VIEW)
    return _report(db, p)


@router.get("/projects/{project_id}/compare")
def compare(project_id: str, jobs: str = Query(..., max_length=400), user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    p = authorize(db, parse_uuid(project_id, "proyecto"), user, Perm.VIEW)
    ids = [parse_uuid(j, "entrenamiento") for j in jobs.split(",")[:5] if j.strip()]
    out = []
    for jid in ids:
        j = db.get(TrainingJob, jid)
        if j is None or j.project_id != p.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Entrenamiento no encontrado")
        a = db.get(Architecture, j.architecture_id)
        series: dict[int, dict] = {}
        for e, n, v in db.execute(select(TrainingMetric.epoch, TrainingMetric.metric_name, TrainingMetric.metric_value)
                                  .where(TrainingMetric.job_id == j.id).order_by(TrainingMetric.epoch)):
            series.setdefault(e, {"epoch": e})[n] = v
        out.append({"job_id": str(j.id), "label": f"{a.name} v{a.version} · {j.params_json.get('optimizer')} lr={j.params_json.get('learning_rate')}",
                    "family": a.family, "status": j.status, "params": j.params_json, "total_params": a.summary_json.get("total_params"),
                    "evaluation": j.result_json.get("evaluation", {}), "epochs": list(series.values())})
    return out


@router.get("/projects/{project_id}/export.csv")
def export_csv(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = authorize(db, parse_uuid(project_id, "proyecto"), user, Perm.EXPORT)
    rows = _history(db, p)
    buf = io.StringIO()
    cols = list(rows[0].keys()) if rows else ["job_id"]
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)
    record(db, user.id, p.id, "report.exported", {"format": "csv"})
    db.commit()
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="aurora-viii-historial.csv"'})


@router.get("/projects/{project_id}/report.pdf")
def export_pdf(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    p = authorize(db, parse_uuid(project_id, "proyecto"), user, Perm.EXPORT)
    r = _report(db, p)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.4 * cm, bottomMargin=1.4 * cm, title=f"Aurora VIII · {p.name}")
    ss = getSampleStyleSheet()
    h1, h2, body = ss["Title"], ss["Heading2"], ss["BodyText"]
    ink = colors.HexColor("#1b1f3b")
    el = [Paragraph("AURORA VIII · Ficha de proyecto", ss["Heading4"]), Paragraph(escape(p.name), h1),
          Paragraph(f"Generado: {r['generated_at'][:19].replace('T', ' ')} UTC · Estado: {p.status}", body), Spacer(1, 8)]
    if p.description:
        el += [Paragraph("<b>Descripción.</b> " + escape(p.description), body)]
    if p.problem:
        el += [Paragraph("<b>Problema.</b> " + escape(p.problem), body)]

    def table(data, widths=None):
        t = Table(data, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), ink), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c8cbe0")),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4fa")]),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    el += [Spacer(1, 10), Paragraph("Arquitecturas", h2)]
    if r["architectures"]:
        el.append(table([["Nombre", "Versión", "Familia", "Parámetros", "Capas"]] +
                        [[a["name"], a["version"], a["family"], f"{a['total_params']:,}",
                          Paragraph("<br/>".join(escape(x) for x in a["layers"]), body)] for a in r["architectures"]],
                        [5 * cm, 2 * cm, 3 * cm, 3 * cm, 13 * cm]))
    el += [Spacer(1, 10), Paragraph("Historial de entrenamiento", h2)]
    if r["history"]:
        fmt = lambda v: "—" if v is None else (f"{v:.4f}" if isinstance(v, float) else str(v))  # noqa: E731
        el.append(table([["Fecha", "Arquitectura", "Dataset", "Estado", "Épocas", "Optim.", "LR", "Duración (s)", "Loss test", "Acc test"]] +
                        [[h["fecha"][:16].replace("T", " "), h["arquitectura"], h["dataset"], h["estado"],
                          f"{h['epocas']}/{h['epocas_totales']}", h["optimizador"], fmt(h["learning_rate"]),
                          fmt(h["duracion_s"]), fmt(h["test_loss"]), fmt(h["test_accuracy"])] for h in r["history"]]))
    el += [Spacer(1, 10), Paragraph("Registro de modelos", h2)]
    if r["models"]:
        el.append(table([["Versión", "Estado", "Checksum (SHA-256)", "Métricas"]] +
                        [[m["version"], m["status"], m["checksum"] + "…",
                          ", ".join(f"{k}={v:.4f}" for k, v in m["metrics"].items() if isinstance(v, (int, float)))]
                         for m in r["models"]]))
    doc.build(el)
    record(db, user.id, p.id, "report.exported", {"format": "pdf"})
    db.commit()
    return Response(buf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="aurora-viii-ficha.pdf"'})
