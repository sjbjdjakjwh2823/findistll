from fastapi import APIRouter, HTTPException, Depends

from app.core.auth import get_current_user
from app.db.registry import get_db
from app.services.license_service import LicenseService

router = APIRouter(prefix='/license', tags=['license'])


@router.post('/validate')
async def validate_license(license_key: str, current_user = Depends(get_current_user)):
    service = LicenseService(get_db())
    result = await service.validate(license_key, current_user.user_id)
    if result['status'] != 'active':
        raise HTTPException(status_code=403, detail=f"License is {result['status']}")
    return result


@router.get('/status')
async def license_status(current_user = Depends(get_current_user)):
    from os import getenv
    license_key = getenv('LICENSE_KEY')
    if not license_key:
        raise HTTPException(status_code=401, detail='Missing license key')
    service = LicenseService(get_db())
    result = await service.validate(license_key, current_user.user_id)
    if result['status'] != 'active':
        raise HTTPException(status_code=403, detail=result)
    return result
