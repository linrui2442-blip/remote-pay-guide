from fastapi import APIRouter
from production.results.manager import get_results, get_result, get_result_by_job

router = APIRouter()

@router.get('/production/results')
def production_results():
    return get_results()

@router.get('/production/results/{result_id}')
def production_result(result_id: int):
    return get_result(result_id)

@router.get('/production/results/job/{runtime_job_id}')
def production_result_job(runtime_job_id: int):
    return get_result_by_job(runtime_job_id)
