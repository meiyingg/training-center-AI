import os
import tempfile
from datetime import date

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="tcms-test-")
os.environ["ALLOW_DEMO_RESET"] = "true"
os.environ["APP_ENV"] = "test"

import pytest
from fastapi.testclient import TestClient

from backend import db
from backend.main import app


@pytest.fixture
def client():
    db.reset_db()
    with TestClient(app) as test_client:
        yield test_client


def login(client, username="admin", password="admin123", remember=False):
    response = client.post("/api/auth/login", json={
        "username": username, "password": password, "remember": remember
    })
    assert response.status_code == 200, response.json()
    return response.json()["data"]["csrfToken"]


def auth(token):
    return {"X-CSRF-Token": token}


@pytest.fixture
def admin(client):
    return client, login(client)


def test_health_and_login_required(client):
    assert client.get("/api/health").json()["data"]["version"] == "3.3.0"
    assert client.get("/api/customers").status_code == 401
    assert client.get("/api/users", headers={"X-Role": "admin"}).status_code == 401


def test_remember_login_uses_secure_signed_cookie(client):
    response = client.post("/api/auth/login", json={
        "username": "admin", "password": "admin123", "remember": True
    })
    assert response.status_code == 200
    remembered = response.cookies.get("tcms_remember")
    assert remembered and "admin123" not in remembered
    with TestClient(app) as fresh_client:
        fresh_client.cookies.set("tcms_remember", remembered)
        me = fresh_client.get("/api/auth/me")
        assert me.status_code == 200, me.json()
        assert me.json()["data"]["role"] == "admin"


def test_repeated_login_failures_do_not_lock_the_device(client):
    for _ in range(6):
        failed = client.post("/api/auth/login", json={
            "username": "admin", "password": "wrong-password"
        })
        assert failed.status_code == 401

    successful = client.post("/api/auth/login", json={
        "username": "admin", "password": "admin123"
    })
    assert successful.status_code == 200, successful.json()


def test_public_registration_is_closed(client):
    response = client.post("/api/auth/register", json={
        "username": "student_new", "password": "password123", "name": "新学生", "phone": "13800000000"
    })
    assert response.status_code == 403


def test_customer_crud_and_convert(admin):
    client, token = admin
    response = client.post("/api/customers", headers=auth(token), json={
        "name": "测试客户", "phone": "13800009999", "contact": "微信", "interest": "英语"
    })
    assert response.status_code == 201, response.json()
    cid = response.json()["data"]["id"]
    assert len(client.get("/api/customers?q=测试").json()["data"]) == 1
    updated = client.put(f"/api/customers/{cid}", headers=auth(token), json={"status": "enrolled"})
    assert updated.json()["data"]["status"] == "enrolled"
    converted = client.post(f"/api/customers/{cid}/convert", headers=auth(token))
    assert converted.status_code == 201
    assert client.delete(f"/api/customers/{cid}", headers=auth(token)).status_code == 200


def test_customer_followups_and_due_dashboard(admin):
    client, token = admin
    customer = client.post("/api/customers", headers=auth(token), json={
        "name": "待跟进客户", "phone": "13800008888", "contact": "微信", "interest": "英语"
    }).json()["data"]
    created = client.post(f"/api/customers/{customer['id']}/followups", headers=auth(token), json={
        "method": "微信", "note": "已发送试听课介绍", "result": "等待确认",
        "nextDate": date.today().isoformat()
    })
    assert created.status_code == 201, created.json()
    followup = created.json()["data"]
    records = client.get(f"/api/customers/{customer['id']}/followups").json()["data"]
    assert len(records) == 1
    assert records[0]["note"] == "已发送试听课介绍"
    dashboard = client.get("/api/dashboard").json()["data"]
    assert any(item["customerId"] == customer["id"] for item in dashboard["dueFollowups"])
    assert client.delete(
        f"/api/customers/{customer['id']}/followups/{followup['id']}", headers=auth(token)
    ).status_code == 200


def test_operations_report_and_permissions(admin):
    client, _ = admin
    report = client.get("/api/reports?days=30")
    assert report.status_code == 200, report.json()
    data = report.json()["data"]
    assert data["period"]["days"] == 30
    assert set(data["summary"]) >= {"courses", "courseHours", "attendanceRate", "conversionRate"}
    assert len(data["daily"]) == 30
    assert client.get("/api/reports?days=8").status_code == 400
    login(client, "teacher1", "123456")
    assert client.get("/api/reports").status_code == 403


def test_non_admin_cannot_manage_customers(client):
    token = login(client, "teacher1", "123456")
    assert client.get("/api/customers").status_code == 403
    assert client.post("/api/customers", headers=auth(token), json={
        "name": "越权", "phone": "13800000001"
    }).status_code == 403


def test_roles_are_fixed_and_accounts_come_from_profiles(admin):
    client, token = admin
    # /api/users only creates admins; teacher/student accounts come from profiles
    for role in ("teacher", "student"):
        assert client.post("/api/users", headers=auth(token), json={
            "username": f"x_{role}", "password": "password123", "role": role, "name": "越权"
        }).status_code == 400
    created = client.post("/api/users", headers=auth(token), json={
        "username": "admin_two", "password": "password123", "role": "admin", "name": "管理员二"
    })
    assert created.status_code == 201, created.json()
    uid = created.json()["data"]["id"]
    assert client.post(f"/api/users/{uid}/role", headers=auth(token), json={"role": "student"}).status_code == 405
    assert all(u["role"] == "admin" for u in client.get("/api/users").json()["data"])
    assert client.post(f"/api/users/{uid}/reset-password", headers=auth(token),
                       json={"password": "newpass123"}).status_code == 200


def test_student_profile_creates_and_resets_login_account(admin):
    client, token = admin
    created = client.post("/api/students", headers=auth(token), json={
        "name": "开户学生", "createAccount": True, "password": "StartPass123"
    })
    assert created.status_code == 201, created.json()
    student = created.json()["data"]
    assert student["account"]["username"] and "password" not in student["account"]
    assert client.post(f"/api/students/{student['id']}/account", headers=auth(token),
                       json={"password": "AnotherPass123"}).status_code == 409
    assert client.post(f"/api/students/{student['id']}/account/reset-password", headers=auth(token),
                       json={"password": "ChangedPass123"}).status_code == 200
    client.post("/api/auth/logout", headers=auth(token))
    login(client, student["account"]["username"], "ChangedPass123")


def test_teacher_profile_can_create_and_reset_login_account(admin):
    client, token = admin
    created = client.post("/api/teachers", headers=auth(token), json={
        "name": "账号老师", "phone": "13911112222", "subject": "英语",
        "createAccount": True, "username": "teacher_account", "password": "StartPass123"
    })
    assert created.status_code == 201, created.json()
    teacher = created.json()["data"]
    assert teacher["account"]["username"] == "teacher_account"
    assert "password" not in teacher["account"]
    reset = client.post(f"/api/teachers/{teacher['id']}/account/reset-password",
                        headers=auth(token), json={"password": "ChangedPass123"})
    assert reset.status_code == 200, reset.json()
    assert client.post("/api/auth/login", json={
        "username": "teacher_account", "password": "ChangedPass123"
    }).status_code == 200


def test_teacher_username_is_generated_from_name_with_duplicate_suffix(admin):
    client, token = admin
    usernames = []
    for _ in range(2):
        response = client.post("/api/teachers", headers=auth(token), json={
            "name": "王老师", "subject": "数学", "createAccount": True,
            "password": "InitialPass123"
        })
        assert response.status_code == 201, response.json()
        usernames.append(response.json()["data"]["account"]["username"])
    # The base is derived from the name (pinyin when pypinyin is installed,
    # otherwise the raw name); the duplicate must only differ by a "2" suffix.
    assert usernames[1] == usernames[0] + "2"
    assert usernames[0] and usernames[0][-1] != "2"


def test_complete_student_profile_and_status_filter(admin):
    client, token = admin
    created = client.post("/api/students", headers=auth(token), json={
        "name": "完整学生", "phone": "13711112222", "email": "student@example.com",
        "gender": "女", "birthDate": "2012-05-06", "school": "实验中学", "grade": "初二",
        "guardianName": "学生家长", "guardianPhone": "13611112222",
        "address": "测试路 1 号", "notes": "需要关注英语口语", "status": "inactive"
    })
    assert created.status_code == 201, created.json()
    student = created.json()["data"]
    assert student["guardianName"] == "学生家长"
    assert student["birthDate"] == "2012-05-06"
    assert student["status"] == "inactive"
    inactive = client.get("/api/students?status=inactive&q=学生家长").json()["data"]
    assert any(item["id"] == student["id"] for item in inactive)
    active = client.get("/api/students?status=active").json()["data"]
    assert all(item["id"] != student["id"] for item in active)


def make_account(client, token, kind, name, username, password):
    body = {"name": name, "createAccount": True, "username": username, "password": password}
    response = client.post(f"/api/{kind}s", headers=auth(token), json=body)
    assert response.status_code == 201, response.json()
    return response.json()["data"]


def create_course_fixture(client, token, date="2026-12-01"):
    teacher = client.post("/api/teachers", headers=auth(token), json={"name": "排课老师"}).json()["data"]
    student = client.post("/api/students", headers=auth(token), json={"name": "排课学生"}).json()["data"]
    course = client.post("/api/courses", headers=auth(token), json={
        "date": date, "start": "09:00", "end": "10:00", "teacherId": teacher["id"],
        "topic": "英语口语", "studentIds": [student["id"]]
    })
    assert course.status_code == 201, course.json()
    return teacher, student, course.json()["data"]


def test_course_conflict_and_attendance(admin):
    client, token = admin
    teacher, student, course = create_course_fixture(client, token)
    conflict = client.post("/api/courses", headers=auth(token), json={
        "date": course["date"], "start": "09:30", "end": "10:30", "teacherId": teacher["id"],
        "topic": "冲突课程", "studentIds": [student["id"]]
    })
    assert conflict.status_code == 409
    signed = client.post("/api/checkins", headers=auth(token), json={
        "courseId": course["id"], "studentId": student["id"]
    })
    assert signed.status_code == 201
    assert client.post("/api/checkins", headers=auth(token), json={
        "courseId": course["id"], "studentId": student["id"]
    }).status_code == 409
    attendance = client.get(f"/api/courses/{course['id']}/attendance").json()["data"]
    assert attendance["signedCount"] == 1 and attendance["total"] == 1


def test_teacher_can_only_access_own_course(admin):
    client, token = admin
    _, _, course = create_course_fixture(client, token)
    make_account(client, token, "teacher", "其他老师", "other_teacher", "teacher123")
    client.post("/api/auth/logout", headers=auth(token))
    teacher_token = login(client, "other_teacher", "teacher123")
    assert client.get(f"/api/courses/{course['id']}").status_code == 403
    assert client.get(f"/api/courses/{course['id']}/attendance").status_code == 403
    assert client.post("/api/checkins", headers=auth(teacher_token), json={
        "courseId": course["id"], "studentId": course["studentIds"][0]
    }).status_code == 403


def test_student_self_checkin(admin):
    client, token = admin
    student = make_account(client, token, "student", "自签学生", "self_student", "student123")
    teacher = client.post("/api/teachers", headers=auth(token), json={"name": "任课老师"}).json()["data"]
    course = client.post("/api/courses", headers=auth(token), json={
        "date": "2026-12-03", "start": "09:00", "end": "10:00", "teacherId": teacher["id"],
        "topic": "自助签到", "studentIds": [student["id"]]
    }).json()["data"]
    client.post("/api/auth/logout", headers=auth(token))
    student_token = login(client, "self_student", "student123")
    response = client.post("/api/checkins", headers=auth(student_token), json={"courseId": course["id"]})
    assert response.status_code == 201, response.json()
    assert client.get(f"/api/courses/{course['id']}/attendance").status_code == 403


def test_batch_courses_with_location_and_weekly_repeat(admin):
    client, token = admin
    teacher = client.post("/api/teachers", headers=auth(token), json={"name": "周课老师"}).json()["data"]
    student = client.post("/api/students", headers=auth(token), json={"name": "周课学生"}).json()["data"]
    body = {"date": "2026-12-07", "start": "09:00", "end": "10:00", "teacherId": teacher["id"],
            "topic": "周课", "location": "201教室", "studentIds": [student["id"]], "repeatWeeks": 4}
    created = client.post("/api/courses/batch", headers=auth(token), json=body)
    assert created.status_code == 201, created.json()
    items = created.json()["data"]
    assert [c["date"] for c in items] == ["2026-12-07", "2026-12-14", "2026-12-21", "2026-12-28"]
    assert all(c["location"] == "201教室" for c in items)
    assert client.post("/api/courses/batch", headers=auth(token), json=body).status_code == 409


def test_csrf_is_required(admin):
    client, _ = admin
    response = client.post("/api/customers", json={"name": "CSRF", "phone": "13800000002"})
    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"


def test_logs_are_admin_only_and_do_not_contain_password(client):
    secret = "not-logged-password"
    client.post("/api/auth/login", json={"username": "admin", "password": secret})
    assert client.get("/api/logs").status_code == 401
    token = login(client)
    payload = client.get("/api/logs").json()
    assert secret not in str(payload)
    assert client.post("/api/logs/clear", headers=auth(token)).status_code == 200


def test_reset_disabled_without_explicit_flag(admin):
    client, token = admin
    os.environ["ALLOW_DEMO_RESET"] = "false"
    try:
        assert client.post("/api/reset", headers=auth(token)).status_code == 403
    finally:
        os.environ["ALLOW_DEMO_RESET"] = "true"
