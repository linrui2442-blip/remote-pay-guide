from fastapi import APIRouter
from production.runtime.manager import create_job, get_jobs, get_job
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
    return {'status':'not_found'} if job is None else worker.run(job)

@router.get('/production/runtime/status')
def runtime_status():
    return {'status':'ready'}
