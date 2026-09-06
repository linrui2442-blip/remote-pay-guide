from fastapi import APIRouter, HTTPException

from production.runtime.manager import create_job, get_jobs, get_job
from production.runtime.poller import runtime_poller
from production.runtime.worker import ProductionRuntimeWorker

router = APIRouter()
worker = ProductionRuntimeWorker()


@router.post('/production/runtime/jobs')
def create_runtime_job(data: dict):
    return create_job(data)


@router.get('/production/runtime/jobs')
def runtime_jobs():
    return get_jobs()


@router.get('/production/runtime/jobs/{job_id}')
def runtime_job(job_id: int):
    return get_job(job_id)


@router.post('/production/runtime/jobs/{job_id}/run')
def run_runtime_job(job_id: int):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail='runtime job not found')
    return worker.run(job)


@router.post('/production/runtime/jobs/{job_id}/refresh')
def refresh_runtime_job(job_id: int):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail='runtime job not found')
    try:
        return worker.poll(job)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/production/runtime/poller/run-once')
def poll_runtime_jobs_once():
    return runtime_poller.poll_once()


@router.get('/production/runtime/status')
def runtime_status():
    return {
        'status': 'ready',
        'poller': runtime_poller.status(),
    }
