import csv
import hashlib
import io
import logging
import mimetypes
import os
import re
import secrets
import time
from collections import deque
from datetime import date as DateType, timedelta
from pathlib import Path
from typing import Annotated, Callable

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from werkzeug.security import check_password_hash, generate_password_hash

try:
    from . import db
    from .schemas import (
        CheckinInput,
        CourseCreate,
        CourseBatchCreate,
        CourseUpdate,
        CustomerCreate,
        CustomerUpdate,
        FollowupCreate,
        LoginInput,
        PasswordInput,
        RegisterInput,
        ResetPasswordInput,
        StudentCreate,
        StudentAccountCreate,
        StudentIdsInput,
        StudentUpdate,
        TeacherCreate,
        TeacherAccountCreate,
        TeacherUpdate,
        UserCreate,
        UserRoleInput,
    )
except ImportError:
    import db
    from schemas import (
        CheckinInput,
        CourseCreate,
        CourseBatchCreate,
        CourseUpdate,
        CustomerCreate,
        CustomerUpdate,
        FollowupCreate,
        LoginInput,
        PasswordInput,
        RegisterInput,
        ResetPasswordInput,
        StudentCreate,
        StudentAccountCreate,
        StudentIdsInput,
        StudentUpdate,
        TeacherCreate,
        TeacherAccountCreate,
        TeacherUpdate,
        UserCreate,
        UserRoleInput,
    )


BASE_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = BASE_DIR / "frontend" / "dist"

# Windows registry can map .js/.mjs/.css to text/plain, which makes browsers
# refuse the SPA's module scripts. mimetypes lazily reads the registry on first
# guess_type() and clobbers add_type(), so init() first, then override the map.
mimetypes.init()
mimetypes.types_map[".js"] = "text/javascript"
mimetypes.types_map[".mjs"] = "text/javascript"
mimetypes.types_map[".css"] = "text/css"

APP_ENV = os.getenv("APP_ENV", "development").lower()
IS_PRODUCTION = APP_ENV == "production"
SECRET_KEY = os.getenv("SECRET_KEY", "")
if IS_PRODUCTION and len(SECRET_KEY) < 32:
    raise RuntimeError("生产环境必须提供至少32位的 SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = "dev-only-change-before-production"

REMEMBER_COOKIE = "tcms_remember"
REMEMBER_MAX_AGE = 60 * 60 * 24 * 30
remember_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="tcms-remember-v1")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger("tcms")
LOG_BUFFER: deque[dict] = deque(maxlen=1000)


class BufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        LOG_BUFFER.append({
            "ts": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "msg": record.getMessage(),
        })


log.addHandler(BufferHandler())
initial_admin_password = os.getenv("INITIAL_ADMIN_PASSWORD", "admin123")
if IS_PRODUCTION and len(initial_admin_password) < 12:
    raise RuntimeError("生产环境必须提供至少12位的 INITIAL_ADMIN_PASSWORD")
db.init_db(seed_admin_pw=initial_admin_password, seed_demo=not IS_PRODUCTION)

app = FastAPI(
    title="培训机构管理系统 API",
    version="3.3.0",
    docs_url=None if IS_PRODUCTION else "/api/docs",
    redoc_url=None,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="tcms_session",
    max_age=60 * 60 * 8,
    same_site="lax",
    https_only=IS_PRODUCTION,
)
allowed_hosts = [x.strip() for x in os.getenv("ALLOWED_HOSTS", "*").split(",") if x.strip()]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts or ["*"])


class ApiError(Exception):
    def __init__(self, status: int, message: str, code: str | None = None):
        self.status = status
        self.message = message
        self.code = code


def success(data=None, status: int = 200):
    body = {"ok": True}
    if data is not None:
        body["data"] = data
    return JSONResponse(body, status_code=status)


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, exc: ApiError):
    body = {"ok": False, "error": exc.message}
    if exc.code:
        body["code"] = exc.code
    return JSONResponse(body, status_code=exc.status)


FIELD_LABELS = {
    "username": "用户名", "password": "密码", "name": "姓名", "phone": "手机号",
    "old": "原密码", "new": "新密码", "email": "邮箱", "role": "角色", "date": "日期",
    "start": "开始时间", "end": "结束时间", "topic": "课程主题", "teacherId": "授课老师",
    "studentIds": "学生名单", "location": "上课地点", "repeatWeeks": "重复周数",
    "birthDate": "出生日期", "gender": "性别", "grade": "年级", "school": "就读学校",
    "guardianName": "监护人姓名", "guardianPhone": "监护人电话", "address": "家庭地址",
    "notes": "备注", "status": "状态", "subject": "授课科目", "contact": "联系方式",
    "interest": "意向课程", "method": "跟进方式", "note": "跟进内容", "result": "跟进结果",
    "nextDate": "下次跟进日期", "courseId": "课程", "studentId": "学生", "remember": "记住登录",
}


def _zh_validation_message(item: dict) -> str:
    kind = item.get("type", "")
    ctx = item.get("ctx", {}) or {}
    if kind == "missing":
        return "不能为空"
    if kind in ("string_too_short", "too_short"):
        limit = ctx.get("min_length") or ctx.get("min_items")
        return f"长度至少 {limit} 位" if limit else "长度不足"
    if kind in ("string_too_long", "too_long"):
        limit = ctx.get("max_length") or ctx.get("max_items")
        return f"长度不能超过 {limit} 位" if limit else "长度超出限制"
    if kind == "value_error":  # our field_validators raise Chinese messages
        return item.get("msg", "").split("Value error, ", 1)[-1] or "取值不合法"
    if kind in ("literal_error", "enum"):
        return "取值不在允许范围内"
    if kind == "extra_forbidden":
        return "包含不被允许的字段"
    if kind.endswith("_parsing") or kind in ("date_type", "time_type"):
        return "格式不正确"
    if kind.endswith("_type"):
        return "类型不正确"
    return item.get("msg", "输入不合法")


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    errors = []
    for item in exc.errors():
        parts = [str(x) for x in item.get("loc", [])[1:]]
        key = next((p for p in reversed(parts) if not p.isdigit()), "")
        label = FIELD_LABELS.get(key, key)
        message = _zh_validation_message(item)
        errors.append(f"{label}：{message}" if label else message)
    return JSONResponse({"ok": False, "error": "；".join(errors) or "提交的内容不合法"}, status_code=422)


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception):
    log.exception("未处理的服务器错误：%s", exc)
    return JSONResponse({"ok": False, "error": "服务器内部错误，请稍后重试"}, status_code=500)


@app.middleware("http")
async def request_log(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    duration = (time.perf_counter() - started) * 1000
    uid = request.session.get("uid") if "session" in request.scope else None
    log.info("%s %s status=%s dur=%.1fms uid=%s", request.method, request.url.path,
             response.status_code, duration, uid or "-")
    return response


def _username_valid(value: str) -> bool:
    return bool(re.fullmatch(r"[\w-]{3,32}", value, flags=re.UNICODE))


try:
    from pypinyin import lazy_pinyin as _lazy_pinyin
except ImportError:  # pypinyin absent: fall back to keeping the raw name
    _lazy_pinyin = None


def _username_base(name: str, fallback: str) -> str:
    """Build an ASCII pinyin base from a (possibly Chinese) name.

    e.g. 王小明 -> wangxiaoming, Anna李 -> annali. Without pypinyin installed
    it degrades to the previous behavior (keeps the raw name characters)."""
    if _lazy_pinyin:
        romanized = "".join(_lazy_pinyin(name.strip()))
        base = re.sub(r"[^a-z0-9]+", "", romanized.lower())
    else:
        base = ""
    if not base:  # no pinyin available, or name had no convertible content
        base = re.sub(r"[^\w-]+", "", name.strip().lower(), flags=re.UNICODE).strip("_-")
    base = base or fallback
    if len(base) < 3:
        base = f"{fallback}_{base}" if base else fallback
    return base[:28]


def _available_profile_username(name: str, fallback: str) -> str:
    base = _username_base(name, fallback)
    candidate = base
    suffix = 2
    while db.find_user_by_username(candidate):
        tail = str(suffix)
        candidate = f"{base[:32-len(tail)]}{tail}"
        suffix += 1
    return candidate


def _available_teacher_username(name: str) -> str:
    return _available_profile_username(name, "teacher")


def _available_student_username(name: str) -> str:
    return _available_profile_username(name, "student")


def _csrf(request: Request) -> None:
    expected = request.session.get("csrf")
    supplied = request.headers.get("X-CSRF-Token")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and (not expected or not secrets.compare_digest(expected, supplied or "")):
        raise ApiError(403, "安全校验失败，请刷新页面后重试", "csrf_failed")


def _password_fingerprint(pw_hash: str) -> str:
    return hashlib.sha256(pw_hash.encode("utf-8")).hexdigest()[:24]


def _make_remember_token(row: dict) -> str:
    return remember_serializer.dumps({
        "username": row["username"],
        "fingerprint": _password_fingerprint(row["pw_hash"]),
    })


def _remembered_user(request: Request) -> dict | None:
    token = request.cookies.get(REMEMBER_COOKIE)
    if not token:
        return None
    try:
        payload = remember_serializer.loads(token, max_age=REMEMBER_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    row = db.find_user_by_username(payload.get("username") or "")
    if not row:
        return None
    expected = _password_fingerprint(row["pw_hash"])
    if not secrets.compare_digest(expected, payload.get("fingerprint") or ""):
        return None
    public = dict(row)
    public.pop("pw_hash", None)
    return public


def current_user(request: Request):
    uid = request.session.get("uid")
    if not uid:
        remembered = _remembered_user(request)
        if not remembered:
            raise ApiError(401, "请先登录", "need_login")
        _session_user(request, remembered)
        uid = remembered["id"]
    user = db.get_user(uid)
    if not user:
        request.session.clear()
        raise ApiError(401, "登录已失效", "need_login")
    _csrf(request)
    return user


CurrentUser = Annotated[dict, Depends(current_user)]


def require_roles(*roles: str) -> Callable:
    def dependency(user: CurrentUser):
        if user["role"] not in roles:
            raise ApiError(403, "没有权限执行此操作", "forbidden")
        return user
    return dependency


def _session_user(request: Request, user: dict) -> dict:
    token = secrets.token_urlsafe(24)
    request.session.clear()
    request.session.update({"uid": user["id"], "csrf": token})
    return {**user, "csrfToken": token}


def _course_for_user(cid: str, user: dict, allow_student: bool = True) -> dict:
    course = db.get_course(cid)
    if not course:
        raise ApiError(404, "课程不存在")
    role, link_id = user["role"], user.get("link_id")
    allowed = role == "admin"
    if role == "teacher":
        allowed = bool(link_id and course.get("teacherId") == link_id)
    if role == "student" and allow_student:
        allowed = bool(link_id and link_id in course.get("studentIds", []))
    if not allowed:
        raise ApiError(403, "只能访问与自己相关的课程", "forbidden")
    return course


@app.get("/api/health")
def health():
    return success({"status": "up", "version": "3.3.0"})


@app.post("/api/auth/login")
def login(payload: LoginInput, request: Request):
    row = db.find_user_by_username(payload.username)
    if not row or not check_password_hash(row["pw_hash"], payload.password):
        raise ApiError(401, "用户名或密码不正确")
    public = dict(row)
    public.pop("pw_hash", None)
    response = success(_session_user(request, public))
    if payload.remember:
        response.set_cookie(
            REMEMBER_COOKIE,
            _make_remember_token(row),
            max_age=REMEMBER_MAX_AGE,
            httponly=True,
            secure=IS_PRODUCTION,
            samesite="lax",
            path="/",
        )
    else:
        response.delete_cookie(REMEMBER_COOKIE, path="/")
    return response


@app.post("/api/auth/register", status_code=201)
def register(payload: RegisterInput, request: Request):
    raise ApiError(403, "学生账号由机构管理员在学生档案中开通")


@app.get("/api/auth/me")
def me(request: Request, user: CurrentUser):
    token = request.session.get("csrf") or secrets.token_urlsafe(24)
    request.session["csrf"] = token
    return success({**user, "csrfToken": token})


@app.post("/api/auth/logout")
def logout(request: Request, _: CurrentUser):
    request.session.clear()
    response = success({"logout": True})
    response.delete_cookie(REMEMBER_COOKIE, path="/")
    return response


@app.post("/api/auth/password")
def change_password(payload: PasswordInput, request: Request, user: CurrentUser):
    row = db.find_user_by_username(user["username"])
    if not row or not check_password_hash(row["pw_hash"], payload.old):
        raise ApiError(400, "原密码不正确")
    db.set_password(user["id"], generate_password_hash(payload.new))
    response = success({"changed": True})
    response.delete_cookie(REMEMBER_COOKIE, path="/")
    return response


@app.get("/api/customers")
def customers(q: str = "", status: str = "", _: dict = Depends(require_roles("admin"))):
    return success(db.list_customers(q.strip(), status.strip()))


@app.post("/api/customers")
def create_customer(payload: CustomerCreate, _: dict = Depends(require_roles("admin"))):
    return success(db.create_customer(payload.name, payload.phone, payload.contact, payload.interest), 201)


@app.get("/api/customers/{cid}")
def get_customer(cid: str, _: dict = Depends(require_roles("admin"))):
    item = db.get_customer(cid)
    if not item:
        raise ApiError(404, "客户不存在")
    return success(item)


@app.put("/api/customers/{cid}")
def update_customer(cid: str, payload: CustomerUpdate, _: dict = Depends(require_roles("admin"))):
    if not db.get_customer(cid):
        raise ApiError(404, "客户不存在")
    return success(db.update_customer(cid, payload.model_dump(exclude_none=True)))


@app.delete("/api/customers/{cid}")
def delete_customer(cid: str, _: dict = Depends(require_roles("admin"))):
    if not db.delete_customer(cid):
        raise ApiError(404, "客户不存在")
    return success({"deleted": cid})


@app.post("/api/customers/{cid}/convert")
def convert_customer(cid: str, _: dict = Depends(require_roles("admin"))):
    customer, student = db.convert_customer(cid)
    if customer is None:
        raise ApiError(404, "客户不存在")
    if student == "exists":
        raise ApiError(409, "该手机号已是学生")
    return success({"customer": customer, "student": student}, 201)


@app.get("/api/customers/{cid}/followups")
def customer_followups(cid: str, _: dict = Depends(require_roles("admin"))):
    if not db.get_customer(cid):
        raise ApiError(404, "客户不存在")
    return success(db.list_customer_followups(cid))


@app.post("/api/customers/{cid}/followups")
def create_customer_followup(cid: str, payload: FollowupCreate,
                             _: dict = Depends(require_roles("admin"))):
    item = db.create_customer_followup(
        cid, payload.method, payload.note, payload.result,
        payload.nextDate.isoformat() if payload.nextDate else None)
    if not item:
        raise ApiError(404, "客户不存在")
    return success(item, 201)


@app.delete("/api/customers/{cid}/followups/{fid}")
def delete_customer_followup(cid: str, fid: str,
                             _: dict = Depends(require_roles("admin"))):
    if not db.delete_customer_followup(cid, fid):
        raise ApiError(404, "跟进记录不存在")
    return success({"deleted": fid})


@app.get("/api/teachers")
def teachers(q: str = "", _: dict = Depends(require_roles("admin"))):
    return success(db.list_teachers(q.strip()))


@app.get("/api/teachers/username-suggestion")
def teacher_username_suggestion(name: str = Query(min_length=1, max_length=50),
                                _: dict = Depends(require_roles("admin"))):
    return success({"username": _available_teacher_username(name)})


@app.post("/api/teachers")
def create_teacher(payload: TeacherCreate, _: dict = Depends(require_roles("admin"))):
    if not payload.createAccount:
        return success(db.create_teacher(payload.name, payload.phone, payload.subject), 201)
    if not payload.password:
        raise ApiError(400, "开通登录账号时必须设置初始密码")
    username = payload.username or _available_teacher_username(payload.name)
    if db.find_user_by_username(username):
        username = _available_teacher_username(payload.name)
    if not _username_valid(username):
        raise ApiError(400, "用户名格式不合法")
    if len(payload.password) < 8:
        raise ApiError(400, "初始密码至少 8 位")
    teacher, error = db.create_teacher_with_account(
        payload.name, payload.phone, payload.subject, username,
        generate_password_hash(payload.password))
    if error == "username_exists":
        raise ApiError(409, "用户名已存在")
    return success(teacher, 201)


@app.post("/api/teachers/{tid}/account")
def create_teacher_account(tid: str, payload: TeacherAccountCreate,
                           _: dict = Depends(require_roles("admin"))):
    teacher = db.get_teacher(tid)
    if not teacher:
        raise ApiError(404, "老师不存在")
    username = payload.username or _available_teacher_username(teacher["name"])
    if db.find_user_by_username(username):
        username = _available_teacher_username(teacher["name"])
    if not _username_valid(username):
        raise ApiError(400, "用户名格式不合法")
    account, error = db.create_teacher_account(
        tid, username, generate_password_hash(payload.password))
    if error == "not_found":
        raise ApiError(404, "老师不存在")
    if error == "has_account":
        raise ApiError(409, "该老师已经开通登录账号")
    if error == "username_exists":
        raise ApiError(409, "用户名已存在")
    return success(account, 201)


@app.post("/api/teachers/{tid}/account/reset-password")
def reset_teacher_account_password(tid: str, payload: ResetPasswordInput,
                                   _: dict = Depends(require_roles("admin"))):
    if not db.reset_teacher_password(tid, generate_password_hash(payload.password)):
        raise ApiError(404, "该老师尚未开通登录账号")
    return success({"reset": True})


@app.get("/api/teachers/{tid}")
def get_teacher(tid: str, _: dict = Depends(require_roles("admin"))):
    item = db.get_teacher(tid)
    if not item:
        raise ApiError(404, "老师不存在")
    return success(item)


@app.put("/api/teachers/{tid}")
def update_teacher(tid: str, payload: TeacherUpdate, _: dict = Depends(require_roles("admin"))):
    if not db.get_teacher(tid):
        raise ApiError(404, "老师不存在")
    return success(db.update_teacher(tid, payload.model_dump(exclude_none=True)))


@app.delete("/api/teachers/{tid}")
def delete_teacher(tid: str, _: dict = Depends(require_roles("admin"))):
    result = db.delete_teacher(tid)
    if result == "has_courses":
        raise ApiError(409, "该老师还有课程，请先调课")
    if not result:
        raise ApiError(404, "老师不存在")
    return success({"deleted": tid})


@app.get("/api/students")
def students(q: str = "", status: str = "", _: dict = Depends(require_roles("admin"))):
    return success(db.list_students(q.strip(), status))


@app.get("/api/students/username-suggestion")
def student_username_suggestion(name: str = Query(min_length=1, max_length=50),
                                _: dict = Depends(require_roles("admin"))):
    return success({"username": _available_student_username(name)})


def _student_values(payload: StudentCreate | StudentUpdate) -> dict:
    values = payload.model_dump(exclude_none=True)
    mapping = {"from_": "from_cid", "birthDate": "birth_date",
               "guardianName": "guardian_name", "guardianPhone": "guardian_phone"}
    output = {mapping.get(key, key): value for key, value in values.items()}
    if "birth_date" in output:
        output["birth_date"] = output["birth_date"].isoformat()
    return output


@app.post("/api/students")
def create_student(payload: StudentCreate, _: dict = Depends(require_roles("admin"))):
    values = _student_values(payload)
    create_account = values.pop("createAccount", False)
    username = values.pop("username", "")
    password = values.pop("password", "")
    if not create_account:
        return success(db.create_student(**values), 201)
    if not password:
        raise ApiError(400, "开通学生账号时必须设置初始密码")
    username = username or _available_student_username(values["name"])
    if db.find_user_by_username(username):
        username = _available_student_username(values["name"])
    if not _username_valid(username):
        raise ApiError(400, "用户名格式不合法")
    student, error = db.create_student_with_account(values, username, generate_password_hash(password))
    if error == "username_exists":
        raise ApiError(409, "用户名已存在")
    return success(student, 201)


@app.post("/api/students/{sid}/account")
def create_student_account(sid: str, payload: StudentAccountCreate,
                           _: dict = Depends(require_roles("admin"))):
    student = db.get_student(sid)
    if not student:
        raise ApiError(404, "学生不存在")
    username = payload.username or _available_student_username(student["name"])
    if db.find_user_by_username(username):
        username = _available_student_username(student["name"])
    if not _username_valid(username):
        raise ApiError(400, "用户名格式不合法")
    account, error = db.create_student_account(sid, username, generate_password_hash(payload.password))
    if error == "has_account":
        raise ApiError(409, "该学生已经开通登录账号")
    if error == "username_exists":
        raise ApiError(409, "用户名已存在")
    return success(account, 201)


@app.post("/api/students/{sid}/account/reset-password")
def reset_student_account_password(sid: str, payload: ResetPasswordInput,
                                   _: dict = Depends(require_roles("admin"))):
    if not db.reset_student_password(sid, generate_password_hash(payload.password)):
        raise ApiError(404, "该学生尚未开通登录账号")
    return success({"reset": True})


@app.get("/api/students/{sid}")
def get_student(sid: str, _: dict = Depends(require_roles("admin"))):
    item = db.get_student(sid)
    if not item:
        raise ApiError(404, "学生不存在")
    return success({**item, "stats": db.student_stats(sid)})


@app.put("/api/students/{sid}")
def update_student(sid: str, payload: StudentUpdate, _: dict = Depends(require_roles("admin"))):
    if not db.get_student(sid):
        raise ApiError(404, "学生不存在")
    return success(db.update_student(sid, _student_values(payload)))


@app.delete("/api/students/{sid}")
def delete_student(sid: str, _: dict = Depends(require_roles("admin"))):
    if not db.delete_student(sid):
        raise ApiError(404, "学生不存在")
    return success({"deleted": sid})


@app.get("/api/students/{sid}/stats")
def student_stats(sid: str, _: dict = Depends(require_roles("admin"))):
    if not db.get_student(sid):
        raise ApiError(404, "学生不存在")
    return success(db.student_stats(sid))


def _course_values(payload: CourseCreate | CourseUpdate) -> dict:
    values = payload.model_dump(exclude_none=True)
    for key in ("date", "start", "end"):
        if key in values:
            values[key] = values[key].isoformat(timespec="minutes") if key in {"start", "end"} else values[key].isoformat()
    return values


@app.get("/api/courses/all")
def all_courses(user: CurrentUser):
    if user["role"] == "admin":
        return success(db.list_courses(include_canceled=True))
    return success(db.list_courses(role=user["role"], me=user.get("link_id"), include_canceled=True))


@app.get("/api/courses")
def courses(user: CurrentUser, date: str = "", teacherId: str = "", studentId: str = ""):
    if user["role"] != "admin":
        teacherId = ""
        studentId = ""
    return success(db.list_courses(role=user["role"], me=user.get("link_id"), date=date,
                                   teacher_id=teacherId, student_id=studentId))


@app.post("/api/courses")
def create_course(payload: CourseCreate, _: dict = Depends(require_roles("admin"))):
    values = _course_values(payload)
    if values["start"] >= values["end"]:
        raise ApiError(400, "结束时间须晚于开始时间")
    conflict = db.find_conflict(values["teacherId"], values["date"], values["start"], values["end"])
    if conflict:
        raise ApiError(409, f"时间冲突：{conflict['date']} {conflict['start']}-{conflict['end']} {conflict['topic']}")
    course, error = db.create_course(values["date"], values["start"], values["end"],
                                     values["teacherId"], values["topic"], values["studentIds"],
                                     values.get("location", ""))
    if error == "no_teacher":
        raise ApiError(404, "老师不存在")
    return success(course, 201)


@app.post("/api/courses/batch")
def create_courses_batch(payload: CourseBatchCreate, _: dict = Depends(require_roles("admin"))):
    values = _course_values(payload)
    if values["start"] >= values["end"]:
        raise ApiError(400, "结束时间须晚于开始时间")
    first_day = DateType.fromisoformat(values["date"])
    dates = [(first_day + timedelta(days=7 * offset)).isoformat()
             for offset in range(values["repeatWeeks"])]
    if not db.get_teacher(values["teacherId"]):
        raise ApiError(404, "老师不存在")
    for course_date in dates:
        conflict = db.find_conflict(values["teacherId"], course_date, values["start"], values["end"])
        if conflict:
            raise ApiError(409, f"{course_date} 时间冲突：{conflict['start']}-{conflict['end']} {conflict['topic']}")
    created = []
    for course_date in dates:
        course, error = db.create_course(course_date, values["start"], values["end"],
                                         values["teacherId"], values["topic"], values["studentIds"],
                                         values.get("location", ""))
        if error:
            raise ApiError(400, "批量排课未完成")
        created.append(course)
    return success(created, 201)


@app.get("/api/courses/{cid}")
def get_course(cid: str, user: CurrentUser):
    return success(_course_for_user(cid, user))


@app.put("/api/courses/{cid}")
def update_course(cid: str, payload: CourseUpdate, _: dict = Depends(require_roles("admin"))):
    current = db.get_course(cid)
    if not current:
        raise ApiError(404, "课程不存在")
    values = _course_values(payload)
    merged = {**current, **values}
    if merged["start"] >= merged["end"]:
        raise ApiError(400, "结束时间须晚于开始时间")
    if not db.get_teacher(merged["teacherId"]):
        raise ApiError(404, "老师不存在")
    conflict = db.find_conflict(merged["teacherId"], merged["date"], merged["start"], merged["end"], ignore=cid)
    if conflict:
        raise ApiError(409, f"时间冲突：{conflict['date']} {conflict['start']}-{conflict['end']} {conflict['topic']}")
    mapping = {"teacherId": "teacher_id"}
    fields = {mapping.get(k, k): v for k, v in values.items() if k in {"date", "start", "end", "teacherId", "topic", "location"}}
    return success(db.update_course(cid, fields, values.get("studentIds") if "studentIds" in values else None))


@app.delete("/api/courses/{cid}")
def delete_course(cid: str, _: dict = Depends(require_roles("admin"))):
    if not db.delete_course(cid):
        raise ApiError(404, "课程不存在")
    return success({"deleted": cid})


@app.post("/api/courses/{cid}/cancel")
def cancel_course(cid: str, _: dict = Depends(require_roles("admin"))):
    item = db.set_canceled(cid, True)
    if not item:
        raise ApiError(404, "课程不存在")
    return success(item)


@app.post("/api/courses/{cid}/restore")
def restore_course(cid: str, _: dict = Depends(require_roles("admin"))):
    item = db.set_canceled(cid, False)
    if not item:
        raise ApiError(404, "课程不存在")
    return success(item)


@app.put("/api/courses/{cid}/students")
def set_course_students(cid: str, payload: StudentIdsInput, _: dict = Depends(require_roles("admin"))):
    if not db.get_course(cid):
        raise ApiError(404, "课程不存在")
    valid_ids = [sid for sid in dict.fromkeys(payload.studentIds) if db.get_student(sid)]
    return success(db.update_course(cid, {}, valid_ids))


@app.get("/api/courses/{cid}/attendance")
def attendance(cid: str, user: CurrentUser):
    _course_for_user(cid, user, allow_student=False)
    return success(db.course_attendance(cid))


@app.get("/api/courses/{cid}/export.csv")
def export_attendance(cid: str, user: CurrentUser):
    _course_for_user(cid, user, allow_student=False)
    data = db.course_attendance(cid)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    course = data["course"]
    writer.writerow(["课程", f"{course['date']} {course['start']}-{course['end']} {course['topic']}"])
    writer.writerow(["姓名", "电话", "状态"])
    for student in data["signed"]:
        writer.writerow([student.get("name"), student.get("phone"), "已到"])
    for student in data["unsigned"]:
        writer.writerow([student.get("name"), student.get("phone"), "未到"])
    return Response("\ufeff" + buffer.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="attendance-{cid}.csv"'})


@app.get("/api/checkins")
def checkins(user: CurrentUser, courseId: str = "", studentId: str = ""):
    if user["role"] == "student":
        studentId = user.get("link_id") or "__none__"
    elif user["role"] == "teacher":
        if not courseId:
            raise ApiError(400, "老师查询签到记录时必须指定课程")
        _course_for_user(courseId, user, allow_student=False)
    return success(db.list_checkins(courseId, studentId))


@app.post("/api/checkins")
def create_checkin(payload: CheckinInput, user: CurrentUser):
    course = _course_for_user(payload.courseId, user)
    sid = payload.studentId
    if user["role"] == "student":
        sid = user.get("link_id")
    elif user["role"] == "teacher":
        _course_for_user(payload.courseId, user, allow_student=False)
    if not sid:
        raise ApiError(400, "缺少学生信息")
    if user["role"] == "student" and sid != user.get("link_id"):
        raise ApiError(403, "只能为自己签到")
    if sid not in course.get("studentIds", []):
        raise ApiError(403, "该学生不在课程名单中")
    item, error = db.create_checkin(payload.courseId, sid)
    if error:
        raise ApiError(error[0], error[1])
    return success(item, 201)


@app.delete("/api/checkins/{cid}/{sid}")
def revoke_checkin(cid: str, sid: str, user: CurrentUser):
    if user["role"] == "student":
        raise ApiError(403, "学生不能撤销签到")
    _course_for_user(cid, user, allow_student=False)
    if not db.delete_checkin(cid, sid):
        raise ApiError(404, "签到记录不存在")
    return success({"revoked": True})


@app.get("/api/dashboard")
def dashboard(user: CurrentUser):
    data = db.dashboard(role=user["role"], me=user.get("link_id"))
    if user["role"] == "teacher":
        data = {key: data[key] for key in ("todayCourses", "todayCourseList", "unsigned")}
    elif user["role"] == "student":
        data = {key: data[key] for key in ("todayCourses", "todayCourseList")}
    return success(data)


@app.get("/api/reports")
def reports(days: int = Query(default=30), _: dict = Depends(require_roles("admin"))):
    if days not in (7, 30, 90):
        raise ApiError(400, "报表周期仅支持 7、30 或 90 天")
    return success(db.operations_report(days))


@app.get("/api/users")
def users(_: dict = Depends(require_roles("admin"))):
    return success([item for item in db.list_users() if item["role"] == "admin"])


@app.post("/api/users")
def create_user(payload: UserCreate, _: dict = Depends(require_roles("admin"))):
    if payload.role != "admin":
        raise ApiError(400, "老师和学生账号请分别在对应档案中开通")
    if not _username_valid(payload.username):
        raise ApiError(400, "用户名格式不合法")
    if db.find_user_by_username(payload.username):
        raise ApiError(409, "用户名已存在")
    link_id = None
    item, error = db.create_user(payload.username, generate_password_hash(payload.password),
                                 payload.role, payload.name, link_id)
    if error:
        raise ApiError(409, "用户名已存在")
    return success(item, 201)


@app.post("/api/users/{uid}/reset-password")
def reset_password(uid: int, payload: ResetPasswordInput, _: dict = Depends(require_roles("admin"))):
    item = db.get_user(uid)
    if not item:
        raise ApiError(404, "用户不存在")
    if item["role"] != "admin":
        raise ApiError(403, "老师和学生密码请在对应档案中重置")
    db.set_password(uid, generate_password_hash(payload.password))
    return success({"reset": True})


@app.post("/api/users/{uid}/role")
def change_role(uid: int, payload: UserRoleInput, admin: dict = Depends(require_roles("admin"))):
    raise ApiError(405, "账号角色创建后不可变更")


@app.delete("/api/users/{uid}")
def delete_user(uid: int, admin: dict = Depends(require_roles("admin"))):
    if uid == admin["id"]:
        raise ApiError(400, "不能删除当前登录账号")
    item = db.get_user(uid)
    if item and item["role"] != "admin":
        raise ApiError(403, "老师和学生账号请在对应档案中管理")
    result = db.delete_user(uid)
    if not result:
        raise ApiError(404, "用户不存在")
    return success({"deleted": uid})


@app.get("/api/logs")
def logs(limit: int = Query(default=200, ge=1, le=1000), _: dict = Depends(require_roles("admin"))):
    return success(list(LOG_BUFFER)[-limit:])


@app.post("/api/logs/clear")
def clear_logs(_: dict = Depends(require_roles("admin"))):
    LOG_BUFFER.clear()
    return success({"cleared": True})


@app.post("/api/reset")
def reset_demo(request: Request, _: dict = Depends(require_roles("admin"))):
    if IS_PRODUCTION or os.getenv("ALLOW_DEMO_RESET", "false").lower() != "true":
        raise ApiError(403, "当前环境未开启演示数据重置")
    db.reset_db()
    request.session.clear()
    return success({"reset": True})


if DIST_DIR.exists():
    assets = DIST_DIR / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def react_app(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = DIST_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST_DIR / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def api_root():
        return success({"service": "training-center-api", "frontend": "run pnpm dev in frontend"})
