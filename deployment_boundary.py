"""Explicit process surface; ordinary deployments retain existing behavior."""
from starlette.responses import JSONResponse


class DeploymentBoundary:
    def __init__(self,app,surface='combined'):
        if surface not in ('combined','teacher','admin'):
            raise ValueError('Invalid deployment surface')
        self.app=app;self.surface=surface

    async def __call__(self,scope,receive,send):
        if scope['type']=='http':
            path=scope.get('path','')
            operations=path=='/api/operations' or path.startswith('/api/operations/')
            allowed_admin=operations or path.startswith(('/api/auth/','/api/account/'))
            # An allowlist closes legacy, undocumented and future restoration routes alike.
            teacher_allowed = path.startswith('/api/auth/') or path in (
                '/api/reading/bootstrap', '/api/reading/theme', '/api/reading/fortune')
            blocked=(self.surface=='teacher' and path.startswith('/api/') and not teacher_allowed) or (
                self.surface=='admin' and path.startswith('/api/') and not allowed_admin)
            if blocked:
                await JSONResponse({'ok':False,'error':'Not found'},status_code=404,
                    headers={'Cache-Control':'no-store'})(scope,receive,send)
                return
        await self.app(scope,receive,send)
