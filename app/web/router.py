from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")

@router.get("/")
async def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")

@router.get("/chat")
async def chat_page(request: Request):
    return templates.TemplateResponse(request=request, name="chat.html")

@router.get("/settings")
async def settings_page(request: Request):
    return templates.TemplateResponse(request=request, name="settings.html")

@router.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@router.get("/servers")
async def servers_page(request: Request):
    return templates.TemplateResponse(request=request, name="servers.html")
