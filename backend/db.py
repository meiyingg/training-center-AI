"""SQLite 数据层：替代原来的 JSON 文件存储。

- 数据库文件：DATA_DIR/tcms.db（支持 DATA_DIR 环境变量隔离，便于测试）
- 开发环境首次建库时写入演示种子数据
- 内置账号：admin/admin123（管理员）、teacher1/123456（老师）、student1/123456（学生）
"""
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta

DATA_DIR = os.environ.get("DATA_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_FILE = os.path.join(DATA_DIR, "tcms.db")

_lock = threading.Lock()


def now():
    return datetime.now().isoformat(timespec="seconds")


def uid(p="id"):
    return p + uuid.uuid4().hex[:6]


def _ensure_column(con, table, column, definition):
    columns = {row["name"] for row in con.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _connect():
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=5)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 5000")
    con.execute("PRAGMA journal_mode = WAL")
    return con


def _seed(con):
    today = datetime.now().date().isoformat()
    t1, t2 = uid("t"), uid("t")
    c1, c2 = uid("c"), uid("c")
    s1, s2 = uid("s"), uid("s")
    k1, k2 = uid("k"), uid("k")
    con.executemany(
        "INSERT INTO customers(id,name,phone,contact,interest,status,created_at) VALUES(?,?,?,?,?,?,?)",
        [(c1, "张小明", "13800001111", "微信同号", "数学", "enrolled", now()),
         (c2, "李咨询", "13900002222", "电话", "英语", "pending", now())])
    con.executemany(
        "INSERT INTO teachers(id,name,phone,subject) VALUES(?,?,?,?)",
        [(t1, "王老师", "13700001111", "数学"),
         (t2, "刘老师", "13600002222", "英语")])
    con.executemany(
        "INSERT INTO students(id,name,phone,from_cid) VALUES(?,?,?,?)",
        [(s1, "张小明", "13800001111", c1),
         (s2, "陈学员", "13500003333", None)])
    con.executemany(
        "INSERT INTO courses(id,date,start,end,teacher_id,topic,canceled) VALUES(?,?,?,?,?,?,0)",
        [(k1, today, "10:00", "11:30", t1, "数学·函数"),
         (k2, today, "14:00", "15:30", t2, "英语·口语")])
    con.executemany(
        "INSERT INTO course_students(course_id,student_id) VALUES(?,?)",
        [(k1, s1), (k1, s2), (k2, s2)])
    return {"t1": t1, "s1": s1}


def init_db(seed_admin_pw="admin123", seed_demo=True):
    """建表 + 可选演示数据 + 内置账号。幂等，可重复调用。"""
    from werkzeug.security import generate_password_hash
    with _lock:
        con = _connect()
        try:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS customers(
              id TEXT PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL,
              contact TEXT DEFAULT '电话', interest TEXT DEFAULT '',
              status TEXT DEFAULT 'pending', created_at TEXT);
            CREATE TABLE IF NOT EXISTS customer_followups(
              id TEXT PRIMARY KEY,
              customer_id TEXT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
              method TEXT NOT NULL DEFAULT '电话', note TEXT NOT NULL,
              result TEXT DEFAULT '', next_date TEXT, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS teachers(
              id TEXT PRIMARY KEY, name TEXT NOT NULL, phone TEXT DEFAULT '', subject TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS students(
              id TEXT PRIMARY KEY, name TEXT NOT NULL, phone TEXT DEFAULT '', from_cid TEXT);
            CREATE TABLE IF NOT EXISTS courses(
              id TEXT PRIMARY KEY, date TEXT NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL,
              teacher_id TEXT NOT NULL, topic TEXT NOT NULL, canceled INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS course_students(
              course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
              student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
              PRIMARY KEY(course_id, student_id));
            CREATE TABLE IF NOT EXISTS checkins(
              course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
              student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
              at TEXT NOT NULL, PRIMARY KEY(course_id, student_id));
            CREATE TABLE IF NOT EXISTS users(
              id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
              pw_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'student',
              name TEXT DEFAULT '', link_id TEXT, created_at TEXT);
            """)
            for column, definition in (
                ("email", "TEXT DEFAULT ''"), ("gender", "TEXT DEFAULT ''"),
                ("birth_date", "TEXT"), ("school", "TEXT DEFAULT ''"),
                ("grade", "TEXT DEFAULT ''"), ("guardian_name", "TEXT DEFAULT ''"),
                ("guardian_phone", "TEXT DEFAULT ''"), ("address", "TEXT DEFAULT ''"),
                ("notes", "TEXT DEFAULT ''"), ("status", "TEXT DEFAULT 'active'"),
            ):
                _ensure_column(con, "students", column, definition)
            _ensure_column(con, "courses", "location", "TEXT DEFAULT ''")
            empty = con.execute("SELECT COUNT(*) c FROM customers").fetchone()["c"] == 0
            links = {}
            if empty and seed_demo:
                links = _seed(con)
            # 内置账号（不存在才建）
            def ensure(username, password, role, name, link_id):
                row = con.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
                if row:
                    return row["id"]
                cur = con.execute(
                    "INSERT INTO users(username,pw_hash,role,name,link_id,created_at) VALUES(?,?,?,?,?,?)",
                    (username, generate_password_hash(password), role, name, link_id, now()))
                return cur.lastrowid
            ensure("admin", seed_admin_pw, "admin", "管理员", None)
            if links:
                ensure("teacher1", "123456", "teacher", "王老师", links.get("t1"))
                ensure("student1", "123456", "student", "张小明", links.get("s1"))
            con.commit()
        finally:
            con.close()


def reset_db(seed_admin_pw="admin123"):
    with _lock:
        con = _connect()
        try:
            con.executescript("""
            DELETE FROM checkins; DELETE FROM course_students; DELETE FROM courses;
            DELETE FROM students; DELETE FROM teachers; DELETE FROM customer_followups;
            DELETE FROM customers; DELETE FROM users;
            """)
            con.commit()
        finally:
            con.close()
    init_db(seed_admin_pw=seed_admin_pw)


# ---------- 通用 ----------
def _row(d):
    return dict(d) if d is not None else None


def _course_dict(r, con=None):
    close = False
    if con is None:
        con = _connect()
        close = True
    try:
        roster = [x["student_id"] for x in con.execute(
            "SELECT student_id FROM course_students WHERE course_id=?", (r["id"],))]
        signed = [x["student_id"] for x in con.execute(
            "SELECT student_id FROM checkins WHERE course_id=?", (r["id"],))]
        teacher = con.execute("SELECT name FROM teachers WHERE id=?", (r["teacher_id"],)).fetchone()
        d = {"id": r["id"], "date": r["date"], "start": r["start"], "end": r["end"],
             "teacherId": r["teacher_id"], "teacherName": teacher["name"] if teacher else "",
             "topic": r["topic"], "location": r["location"],
             "canceled": bool(r["canceled"]), "studentIds": roster,
             "signedCount": len(signed), "signedStudentIds": signed}
        return d
    finally:
        if close:
            con.close()


# ---------- 客户 ----------
def list_customers(q="", status=""):
    con = _connect()
    try:
        sql = "SELECT * FROM customers WHERE 1=1"
        args = []
        if q:
            sql += " AND (name LIKE ? OR phone LIKE ?)"
            args += [f"%{q}%", f"%{q}%"]
        if status in ("pending", "enrolled"):
            sql += " AND status=?"
            args.append(status)
        sql += " ORDER BY created_at DESC"
        out = []
        for row in con.execute(sql, args):
            item = _row(row)
            latest = con.execute(
                "SELECT * FROM customer_followups WHERE customer_id=? ORDER BY created_at DESC LIMIT 1",
                (item["id"],)).fetchone()
            item["followupCount"] = con.execute(
                "SELECT COUNT(*) c FROM customer_followups WHERE customer_id=?",
                (item["id"],)).fetchone()["c"]
            item["lastFollowupAt"] = latest["created_at"] if latest else None
            item["nextFollowup"] = latest["next_date"] if latest else None
            out.append(item)
        return out
    finally:
        con.close()


def get_customer(cid):
    con = _connect()
    try:
        return _row(con.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone())
    finally:
        con.close()


def create_customer(name, phone, contact="电话", interest=""):
    cid = uid("c")
    con = _connect()
    try:
        con.execute(
            "INSERT INTO customers(id,name,phone,contact,interest,status,created_at) VALUES(?,?,?,?,?,'pending',?)",
            (cid, name, phone, contact, interest, now()))
        con.commit()
        return _row(con.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone())
    finally:
        con.close()


def update_customer(cid, fields):
    allowed = ("name", "phone", "contact", "interest", "status")
    sets = [(k, fields[k]) for k in allowed if k in fields]
    if not sets:
        return get_customer(cid)
    con = _connect()
    try:
        con.execute(f"UPDATE customers SET {','.join(k+'=?' for k,_ in sets)} WHERE id=?",
                    [v for _, v in sets] + [cid])
        con.commit()
        return _row(con.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone())
    finally:
        con.close()


def delete_customer(cid):
    con = _connect()
    try:
        cur = con.execute("DELETE FROM customers WHERE id=?", (cid,))
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def convert_customer(cid):
    """客户转学生。返回 (customer, student)；已转过返回 (None, 'exists')；不存在返回 (None, None)。"""
    con = _connect()
    try:
        c = con.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()
        if not c:
            return None, None
        dup = con.execute("SELECT id FROM students WHERE phone=? AND phone<>''",
                          (c["phone"],)).fetchone()
        if dup:
            return None, "exists"
        sid = uid("s")
        con.execute("INSERT INTO students(id,name,phone,from_cid) VALUES(?,?,?,?)",
                    (sid, c["name"], c["phone"], cid))
        con.execute("UPDATE customers SET status='enrolled' WHERE id=?", (cid,))
        con.commit()
        return (_row(con.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()),
                _student_dict(con.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone(), con))
    finally:
        con.close()


def list_customer_followups(cid):
    con = _connect()
    try:
        return [_row(row) for row in con.execute(
            "SELECT * FROM customer_followups WHERE customer_id=? ORDER BY created_at DESC",
            (cid,))]
    finally:
        con.close()


def create_customer_followup(cid, method, note, result="", next_date=None):
    fid = uid("f")
    con = _connect()
    try:
        if not con.execute("SELECT 1 FROM customers WHERE id=?", (cid,)).fetchone():
            return None
        con.execute(
            "INSERT INTO customer_followups(id,customer_id,method,note,result,next_date,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (fid, cid, method, note, result, next_date, now()))
        con.commit()
        return _row(con.execute(
            "SELECT * FROM customer_followups WHERE id=?", (fid,)).fetchone())
    finally:
        con.close()


def delete_customer_followup(cid, fid):
    con = _connect()
    try:
        cur = con.execute(
            "DELETE FROM customer_followups WHERE id=? AND customer_id=?", (fid, cid))
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


# ---------- 老师 ----------
def _teacher_dict(row, con):
    if not row:
        return None
    item = _row(row)
    account = con.execute(
        "SELECT id,username,name,created_at FROM users WHERE role='teacher' AND link_id=? LIMIT 1",
        (item["id"],)).fetchone()
    item["account"] = _row(account)
    return item


def list_teachers(q=""):
    con = _connect()
    try:
        if q:
            rows = con.execute("SELECT * FROM teachers WHERE name LIKE ? OR subject LIKE ? OR phone LIKE ? ORDER BY name",
                               (f"%{q}%", f"%{q}%", f"%{q}%"))
        else:
            rows = con.execute("SELECT * FROM teachers ORDER BY name")
        out = []
        for t in rows:
            d = _teacher_dict(t, con)
            d["courseCount"] = con.execute(
                "SELECT COUNT(*) c FROM courses WHERE teacher_id=? AND canceled=0",
                (t["id"],)).fetchone()["c"]
            out.append(d)
        return out
    finally:
        con.close()


def get_teacher(tid):
    con = _connect()
    try:
        return _teacher_dict(
            con.execute("SELECT * FROM teachers WHERE id=?", (tid,)).fetchone(), con)
    finally:
        con.close()


def create_teacher(name, phone="", subject=""):
    tid = uid("t")
    con = _connect()
    try:
        con.execute("INSERT INTO teachers(id,name,phone,subject) VALUES(?,?,?,?)",
                    (tid, name, phone, subject))
        con.commit()
        return _teacher_dict(
            con.execute("SELECT * FROM teachers WHERE id=?", (tid,)).fetchone(), con)
    finally:
        con.close()


def create_teacher_with_account(name, phone, subject, username, pw_hash):
    tid = uid("t")
    con = _connect()
    try:
        if con.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            return None, "username_exists"
        con.execute("INSERT INTO teachers(id,name,phone,subject) VALUES(?,?,?,?)",
                    (tid, name, phone, subject))
        con.execute(
            "INSERT INTO users(username,pw_hash,role,name,link_id,created_at) VALUES(?,?,'teacher',?,?,?)",
            (username, pw_hash, name, tid, now()))
        con.commit()
        return _teacher_dict(
            con.execute("SELECT * FROM teachers WHERE id=?", (tid,)).fetchone(), con), None
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def create_teacher_account(tid, username, pw_hash):
    con = _connect()
    try:
        teacher = con.execute("SELECT * FROM teachers WHERE id=?", (tid,)).fetchone()
        if not teacher:
            return None, "not_found"
        if con.execute("SELECT 1 FROM users WHERE role='teacher' AND link_id=?", (tid,)).fetchone():
            return None, "has_account"
        if con.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            return None, "username_exists"
        cur = con.execute(
            "INSERT INTO users(username,pw_hash,role,name,link_id,created_at) VALUES(?,?,'teacher',?,?,?)",
            (username, pw_hash, teacher["name"], tid, now()))
        con.commit()
        return _public_user(con.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()), None
    finally:
        con.close()


def reset_teacher_password(tid, pw_hash):
    con = _connect()
    try:
        account = con.execute(
            "SELECT id FROM users WHERE role='teacher' AND link_id=?", (tid,)).fetchone()
        if not account:
            return False
        con.execute("UPDATE users SET pw_hash=? WHERE id=?", (pw_hash, account["id"]))
        con.commit()
        return True
    finally:
        con.close()


def update_teacher(tid, fields):
    allowed = ("name", "phone", "subject")
    sets = [(k, fields[k]) for k in allowed if k in fields]
    con = _connect()
    try:
        if sets:
            con.execute(f"UPDATE teachers SET {','.join(k+'=?' for k,_ in sets)} WHERE id=?",
                        [v for _, v in sets] + [tid])
            con.commit()
        return _teacher_dict(
            con.execute("SELECT * FROM teachers WHERE id=?", (tid,)).fetchone(), con)
    finally:
        con.close()


def delete_teacher(tid):
    con = _connect()
    try:
        n = con.execute("SELECT COUNT(*) c FROM courses WHERE teacher_id=? AND canceled=0",
                        (tid,)).fetchone()["c"]
        if n:
            return "has_courses"
        con.execute("DELETE FROM users WHERE role='teacher' AND link_id=?", (tid,))
        cur = con.execute("DELETE FROM teachers WHERE id=?", (tid,))
        con.commit()
        return True if cur.rowcount else False
    finally:
        con.close()


# ---------- 学生 ----------
def _student_dict(row, con=None):
    if not row:
        return None
    close = con is None
    if close:
        con = _connect()
    item = _row(row)
    item["from"] = item.pop("from_cid", None)
    for source, target in (
        ("birth_date", "birthDate"), ("guardian_name", "guardianName"),
        ("guardian_phone", "guardianPhone"),
    ):
        item[target] = item.pop(source, None)
    try:
        account = con.execute(
            "SELECT id,username,name,created_at FROM users WHERE role='student' AND link_id=? LIMIT 1",
            (item["id"],)).fetchone()
        item["account"] = _row(account)
        return item
    finally:
        if close:
            con.close()


def list_students(q="", status=""):
    con = _connect()
    try:
        sql = "SELECT * FROM students WHERE 1=1"
        args = []
        if q:
            sql += (" AND (name LIKE ? OR phone LIKE ? OR guardian_name LIKE ? "
                    "OR guardian_phone LIKE ? OR school LIKE ?)")
            args.extend([f"%{q}%"] * 5)
        if status in ("active", "inactive"):
            sql += " AND status=?"
            args.append(status)
        sql += " ORDER BY status,name"
        rows = con.execute(sql, args)
        out = []
        for s in rows:
            d = _student_dict(s, con)
            d["courseCount"] = con.execute(
                "SELECT COUNT(*) c FROM course_students cs JOIN courses k ON k.id=cs.course_id "
                "WHERE cs.student_id=? AND k.canceled=0", (s["id"],)).fetchone()["c"]
            d["checkinCount"] = con.execute(
                "SELECT COUNT(*) c FROM checkins WHERE student_id=?", (s["id"],)).fetchone()["c"]
            out.append(d)
        return out
    finally:
        con.close()


def get_student(sid):
    con = _connect()
    try:
        r = con.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
        if not r:
            return None
        return _student_dict(r, con)
    finally:
        con.close()


def create_student(name, phone="", from_cid=None, email="", gender="", birth_date=None,
                   school="", grade="", guardian_name="", guardian_phone="", address="",
                   notes="", status="active"):
    sid = uid("s")
    con = _connect()
    try:
        con.execute(
            "INSERT INTO students(id,name,phone,from_cid,email,gender,birth_date,school,grade,"
            "guardian_name,guardian_phone,address,notes,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (sid, name, phone, from_cid, email, gender, birth_date, school, grade,
             guardian_name, guardian_phone, address, notes, status))
        con.commit()
        return _student_dict(con.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone(), con)
    finally:
        con.close()


def create_student_with_account(values, username, pw_hash):
    sid = uid("s")
    con = _connect()
    try:
        if con.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            return None, "username_exists"
        con.execute(
            "INSERT INTO students(id,name,phone,from_cid,email,gender,birth_date,school,grade,"
            "guardian_name,guardian_phone,address,notes,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (sid, values["name"], values.get("phone", ""), values.get("from_cid"),
             values.get("email", ""), values.get("gender", ""), values.get("birth_date"),
             values.get("school", ""), values.get("grade", ""), values.get("guardian_name", ""),
             values.get("guardian_phone", ""), values.get("address", ""), values.get("notes", ""),
             values.get("status", "active")))
        con.execute(
            "INSERT INTO users(username,pw_hash,role,name,link_id,created_at) VALUES(?,?,'student',?,?,?)",
            (username, pw_hash, values["name"], sid, now()))
        con.commit()
        return _student_dict(con.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone(), con), None
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def create_student_account(sid, username, pw_hash):
    con = _connect()
    try:
        student = con.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
        if not student:
            return None, "not_found"
        if con.execute("SELECT 1 FROM users WHERE role='student' AND link_id=?", (sid,)).fetchone():
            return None, "has_account"
        if con.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            return None, "username_exists"
        cur = con.execute(
            "INSERT INTO users(username,pw_hash,role,name,link_id,created_at) VALUES(?,?,'student',?,?,?)",
            (username, pw_hash, student["name"], sid, now()))
        con.commit()
        return _public_user(con.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()), None
    finally:
        con.close()


def reset_student_password(sid, pw_hash):
    con = _connect()
    try:
        account = con.execute(
            "SELECT id FROM users WHERE role='student' AND link_id=?", (sid,)).fetchone()
        if not account:
            return False
        con.execute("UPDATE users SET pw_hash=? WHERE id=?", (pw_hash, account["id"]))
        con.commit()
        return True
    finally:
        con.close()


def update_student(sid, fields):
    allowed = ("name", "phone", "email", "gender", "birth_date", "school", "grade",
               "guardian_name", "guardian_phone", "address", "notes", "status")
    sets = [(k, fields[k]) for k in allowed if k in fields]
    con = _connect()
    try:
        if sets:
            con.execute(f"UPDATE students SET {','.join(k+'=?' for k,_ in sets)} WHERE id=?",
                        [v for _, v in sets] + [sid])
            con.commit()
        return _student_dict(con.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone(), con)
    finally:
        con.close()


def delete_student(sid):
    con = _connect()
    try:
        con.execute("DELETE FROM users WHERE role='student' AND link_id=?", (sid,))
        cur = con.execute("DELETE FROM students WHERE id=?", (sid,))
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


# ---------- 课程 ----------
def find_conflict(teacher_id, date, start, end, ignore=None):
    con = _connect()
    try:
        sql = ("SELECT * FROM courses WHERE teacher_id=? AND date=? AND canceled=0 "
               "AND start < ? AND ? < end")
        args = [teacher_id, date, end, start]
        if ignore:
            sql += " AND id<>?"
            args.append(ignore)
        r = con.execute(sql, args).fetchone()
        return _row(r)
    finally:
        con.close()


def list_courses(role=None, me=None, date="", teacher_id="", student_id="", include_canceled=False):
    con = _connect()
    try:
        sql = "SELECT * FROM courses WHERE 1=1"
        args = []
        if not include_canceled:
            sql += " AND canceled=0"
        if date:
            sql += " AND date=?"
            args.append(date)
        if teacher_id:
            sql += " AND teacher_id=?"
            args.append(teacher_id)
        if role == "teacher" and me:
            sql += " AND teacher_id=?"
            args.append(me)
        if student_id:
            sql += " AND id IN (SELECT course_id FROM course_students WHERE student_id=?)"
            args.append(student_id)
        if role == "student" and me:
            sql += " AND id IN (SELECT course_id FROM course_students WHERE student_id=?)"
            args.append(me)
        sql += " ORDER BY date, start"
        return [_course_dict(r, con) for r in con.execute(sql, args)]
    finally:
        con.close()


def get_course(cid):
    con = _connect()
    try:
        r = con.execute("SELECT * FROM courses WHERE id=?", (cid,)).fetchone()
        return _course_dict(r, con) if r else None
    finally:
        con.close()


def create_course(date, start, end, teacher_id, topic, student_ids=(), location=""):
    cid = uid("k")
    con = _connect()
    try:
        if not con.execute("SELECT id FROM teachers WHERE id=?", (teacher_id,)).fetchone():
            return None, "no_teacher"
        con.execute(
            "INSERT INTO courses(id,date,start,end,teacher_id,topic,location,canceled) VALUES(?,?,?,?,?,?,?,0)",
            (cid, date, start, end, teacher_id, topic, location))
        for sid in student_ids or []:
            if con.execute("SELECT id FROM students WHERE id=?", (sid,)).fetchone():
                con.execute("INSERT OR IGNORE INTO course_students(course_id,student_id) VALUES(?,?)",
                            (cid, sid))
        con.commit()
        return _course_dict(con.execute("SELECT * FROM courses WHERE id=?", (cid,)).fetchone(), con), None
    finally:
        con.close()


def update_course(cid, fields, student_ids=None):
    con = _connect()
    try:
        r = con.execute("SELECT * FROM courses WHERE id=?", (cid,)).fetchone()
        if not r:
            return None
        allowed = ("date", "start", "end", "teacher_id", "topic", "location")
        sets = [(k, fields[k]) for k in allowed if k in fields]
        if sets:
            con.execute(f"UPDATE courses SET {','.join(k+'=?' for k,_ in sets)} WHERE id=?",
                        [v for _, v in sets] + [cid])
        if student_ids is not None:
            con.execute("DELETE FROM course_students WHERE course_id=?", (cid,))
            for sid in student_ids:
                if con.execute("SELECT id FROM students WHERE id=?", (sid,)).fetchone():
                    con.execute("INSERT OR IGNORE INTO course_students(course_id,student_id) VALUES(?,?)",
                                (cid, sid))
        con.commit()
        return _course_dict(con.execute("SELECT * FROM courses WHERE id=?", (cid,)).fetchone(), con)
    finally:
        con.close()


def delete_course(cid):
    con = _connect()
    try:
        cur = con.execute("DELETE FROM courses WHERE id=?", (cid,))
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def set_canceled(cid, canceled=True):
    con = _connect()
    try:
        con.execute("UPDATE courses SET canceled=? WHERE id=?", (1 if canceled else 0, cid))
        con.commit()
        r = con.execute("SELECT * FROM courses WHERE id=?", (cid,)).fetchone()
        return _course_dict(r, con) if r else None
    finally:
        con.close()


def course_attendance(cid):
    con = _connect()
    try:
        r = con.execute("SELECT * FROM courses WHERE id=?", (cid,)).fetchone()
        if not r:
            return None
        roster = [x["student_id"] for x in con.execute(
            "SELECT student_id FROM course_students WHERE course_id=?", (cid,))]
        signed_ids = {x["student_id"] for x in con.execute(
            "SELECT student_id FROM checkins WHERE course_id=?", (cid,))}
        signed, unsigned = [], []
        for sid in roster:
            s = con.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
            if not s:
                continue
            d = _row(s)
            d["from"] = d.pop("from_cid", None)
            (signed if sid in signed_ids else unsigned).append(d)
        return {"course": _course_dict(r, con), "signed": signed, "unsigned": unsigned,
                "signedCount": len(signed_ids & set(roster)), "total": len(roster)}
    finally:
        con.close()


# ---------- 签到 ----------
def list_checkins(course_id="", student_id=""):
    con = _connect()
    try:
        sql = ("SELECT h.course_id, h.student_id, h.at, s.name AS student_name, k.topic AS course_topic "
               "FROM checkins h LEFT JOIN students s ON s.id=h.student_id "
               "LEFT JOIN courses k ON k.id=h.course_id WHERE 1=1")
        args = []
        if course_id:
            sql += " AND h.course_id=?"
            args.append(course_id)
        if student_id:
            sql += " AND h.student_id=?"
            args.append(student_id)
        sql += " ORDER BY h.at DESC"
        return [{"courseId": r["course_id"], "studentId": r["student_id"], "at": r["at"],
                 "studentName": r["student_name"], "courseTopic": r["course_topic"]}
                for r in con.execute(sql, args)]
    finally:
        con.close()


def create_checkin(course_id, student_id):
    con = _connect()
    try:
        c = con.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
        if not c:
            return None, (404, "课程不存在")
        if c["canceled"]:
            return None, (409, "课程已取消")
        if not con.execute("SELECT 1 FROM course_students WHERE course_id=? AND student_id=?",
                           (course_id, student_id)).fetchone():
            return None, (403, "该学生不在课程名单中")
        if con.execute("SELECT 1 FROM checkins WHERE course_id=? AND student_id=?",
                       (course_id, student_id)).fetchone():
            return None, (409, "每节课限签到一次")
        at = now()
        con.execute("INSERT INTO checkins(course_id,student_id,at) VALUES(?,?,?)",
                    (course_id, student_id, at))
        con.commit()
        return {"courseId": course_id, "studentId": student_id, "at": at}, None
    finally:
        con.close()


def delete_checkin(course_id, student_id):
    """撤销签到（纠错），返回 True/False。"""
    con = _connect()
    try:
        cur = con.execute("DELETE FROM checkins WHERE course_id=? AND student_id=?",
                          (course_id, student_id))
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def student_stats(student_id):
    """单个学生的考勤统计：应到/实到/缺勤/签到率。"""
    con = _connect()
    try:
        total = con.execute(
            "SELECT COUNT(*) c FROM course_students cs JOIN courses k ON k.id=cs.course_id "
            "WHERE cs.student_id=? AND k.canceled=0", (student_id,)).fetchone()["c"]
        done = con.execute(
            "SELECT COUNT(*) c FROM checkins h JOIN courses k ON k.id=h.course_id "
            "WHERE h.student_id=? AND k.canceled=0", (student_id,)).fetchone()["c"]
        rate = round(done / total * 100, 1) if total else 0.0
        return {"total": total, "signed": done, "missed": total - done, "rate": rate}
    finally:
        con.close()


# ---------- 用户 ----------
def create_user(username, pw_hash, role, name="", link_id=None):
    con = _connect()
    try:
        if con.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone():
            return None, "exists"
        cur = con.execute(
            "INSERT INTO users(username,pw_hash,role,name,link_id,created_at) VALUES(?,?,?,?,?,?)",
            (username, pw_hash, role, name, link_id, now()))
        con.commit()
        return _public_user(con.execute("SELECT * FROM users WHERE id=?",
                                        (cur.lastrowid,)).fetchone()), None
    finally:
        con.close()


def find_user_by_username(username):
    con = _connect()
    try:
        return _row(con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone())
    finally:
        con.close()


def get_user(uid_):
    con = _connect()
    try:
        r = con.execute("SELECT * FROM users WHERE id=?", (uid_,)).fetchone()
        return _public_user(r) if r else None
    finally:
        con.close()


def _public_user(r):
    if not r:
        return None
    d = _row(r)
    d.pop("pw_hash", None)
    return d


def list_users():
    con = _connect()
    try:
        return [_public_user(r) for r in con.execute("SELECT * FROM users ORDER BY id")]
    finally:
        con.close()


def delete_user(uid_):
    con = _connect()
    try:
        n = con.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        if n <= 1:
            return "last"
        cur = con.execute("DELETE FROM users WHERE id=?", (uid_,))
        con.commit()
        return True if cur.rowcount else False
    finally:
        con.close()


def set_password(uid_, pw_hash):
    con = _connect()
    try:
        con.execute("UPDATE users SET pw_hash=? WHERE id=?", (pw_hash, uid_))
        con.commit()
        return True
    finally:
        con.close()


def update_user_role(uid_, role, link_id=None):
    con = _connect()
    try:
        con.execute("UPDATE users SET role=?, link_id=? WHERE id=?", (role, link_id, uid_))
        con.commit()
        return _public_user(con.execute("SELECT * FROM users WHERE id=?", (uid_,)).fetchone())
    finally:
        con.close()


# ---------- 总览 ----------
def dashboard(role=None, me=None):
    con = _connect()
    try:
        today = datetime.now().date().isoformat()
        pending = con.execute("SELECT COUNT(*) c FROM customers WHERE status='pending'").fetchone()["c"]
        enrolled = con.execute("SELECT COUNT(*) c FROM customers WHERE status='enrolled'").fetchone()["c"]
        n_tea = con.execute("SELECT COUNT(*) c FROM teachers").fetchone()["c"]
        n_stu = con.execute("SELECT COUNT(*) c FROM students WHERE status='active'").fetchone()["c"]
        n_cou = con.execute("SELECT COUNT(*) c FROM courses WHERE canceled=0").fetchone()["c"]
        sql = "SELECT * FROM courses WHERE canceled=0 AND date=?"
        args = [today]
        if role == "teacher" and me:
            sql += " AND teacher_id=?"
            args.append(me)
        if role == "student" and me:
            sql += " AND id IN (SELECT course_id FROM course_students WHERE student_id=?)"
            args.append(me)
        sql += " ORDER BY start"
        today_courses = [_course_dict(r, con) for r in con.execute(sql, args)]
        unsigned = []
        for c in today_courses:
            for sid in c["studentIds"]:
                if sid not in (c.get("signedStudentIds") or []):
                    s = con.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
                    if s:
                        d = _row(s)
                        d["from"] = d.pop("from_cid", None)
                        unsigned.append({"courseId": c["id"], "courseTopic": c["topic"],
                                         "start": c["start"], "student": d})
        today_checkins = con.execute(
            "SELECT COUNT(*) c FROM checkins h JOIN courses k ON k.id=h.course_id "
            "WHERE k.date=? AND k.canceled=0", (today,)).fetchone()["c"]
        due_followups = []
        if role == "admin":
            rows = con.execute(
                "SELECT c.id,c.name,c.phone,c.interest,f.id AS followup_id,f.method,f.note,"
                "f.result,f.next_date,f.created_at FROM customers c "
                "JOIN customer_followups f ON f.id=(SELECT id FROM customer_followups "
                "WHERE customer_id=c.id ORDER BY created_at DESC LIMIT 1) "
                "WHERE c.status='pending' AND f.next_date IS NOT NULL AND f.next_date<=? "
                "ORDER BY f.next_date,c.name", (today,))
            due_followups = [{"customerId": row["id"], "customerName": row["name"],
                              "phone": row["phone"], "interest": row["interest"],
                              "followupId": row["followup_id"], "method": row["method"],
                              "note": row["note"], "result": row["result"],
                              "nextDate": row["next_date"], "createdAt": row["created_at"]}
                             for row in rows]
        return {"pendingCustomers": pending, "enrolledCustomers": enrolled,
                "teachers": n_tea, "students": n_stu, "courses": n_cou,
                "todayCourses": len(today_courses), "todayCheckins": today_checkins,
                "unsigned": unsigned, "todayCourseList": today_courses,
                "dueFollowups": due_followups}
    finally:
        con.close()


def operations_report(days=30):
    con = _connect()
    try:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days - 1)
        start = start_date.isoformat()
        end = end_date.isoformat()
        course_rows = list(con.execute(
            "SELECT * FROM courses WHERE canceled=0 AND date BETWEEN ? AND ? ORDER BY date",
            (start, end)))
        course_ids = [row["id"] for row in course_rows]
        scheduled = con.execute(
            "SELECT COUNT(*) c FROM course_students cs JOIN courses k ON k.id=cs.course_id "
            "WHERE k.canceled=0 AND k.date BETWEEN ? AND ?", (start, end)).fetchone()["c"]
        signed = con.execute(
            "SELECT COUNT(*) c FROM checkins h JOIN courses k ON k.id=h.course_id "
            "WHERE k.canceled=0 AND k.date BETWEEN ? AND ?", (start, end)).fetchone()["c"]
        new_customers = con.execute(
            "SELECT COUNT(*) c FROM customers WHERE substr(created_at,1,10) BETWEEN ? AND ?",
            (start, end)).fetchone()["c"]
        enrolled_customers = con.execute(
            "SELECT COUNT(*) c FROM customers WHERE status='enrolled' "
            "AND substr(created_at,1,10) BETWEEN ? AND ?", (start, end)).fetchone()["c"]
        course_minutes = 0
        for row in course_rows:
            start_parts = [int(value) for value in row["start"].split(":")[:2]]
            end_parts = [int(value) for value in row["end"].split(":")[:2]]
            course_minutes += max(0, end_parts[0] * 60 + end_parts[1] -
                                  start_parts[0] * 60 - start_parts[1])

        daily = []
        cursor = start_date
        while cursor <= end_date:
            day = cursor.isoformat()
            day_courses = con.execute(
                "SELECT COUNT(*) c FROM courses WHERE canceled=0 AND date=?", (day,)).fetchone()["c"]
            day_scheduled = con.execute(
                "SELECT COUNT(*) c FROM course_students cs JOIN courses k ON k.id=cs.course_id "
                "WHERE k.canceled=0 AND k.date=?", (day,)).fetchone()["c"]
            day_signed = con.execute(
                "SELECT COUNT(*) c FROM checkins h JOIN courses k ON k.id=h.course_id "
                "WHERE k.canceled=0 AND k.date=?", (day,)).fetchone()["c"]
            daily.append({"date": day, "courses": day_courses, "scheduled": day_scheduled,
                          "signed": day_signed,
                          "rate": round(day_signed / day_scheduled * 100, 1) if day_scheduled else 0})
            cursor += timedelta(days=1)

        teacher_rows = con.execute(
            "SELECT t.id,t.name,t.subject,COUNT(DISTINCT k.id) AS course_count,"
            "COUNT(cs.student_id) AS scheduled_count,COUNT(h.student_id) AS signed_count "
            "FROM teachers t LEFT JOIN courses k ON k.teacher_id=t.id AND k.canceled=0 "
            "AND k.date BETWEEN ? AND ? LEFT JOIN course_students cs ON cs.course_id=k.id "
            "LEFT JOIN checkins h ON h.course_id=k.id AND h.student_id=cs.student_id "
            "GROUP BY t.id,t.name,t.subject ORDER BY course_count DESC,t.name", (start, end))
        teachers = [{"id": row["id"], "name": row["name"], "subject": row["subject"],
                     "courseCount": row["course_count"], "scheduled": row["scheduled_count"],
                     "signed": row["signed_count"],
                     "attendanceRate": round(row["signed_count"] / row["scheduled_count"] * 100, 1)
                     if row["scheduled_count"] else 0} for row in teacher_rows]
        return {
            "period": {"days": days, "start": start, "end": end},
            "summary": {"courses": len(course_ids), "courseHours": round(course_minutes / 60, 1),
                        "scheduled": scheduled, "signed": signed,
                        "attendanceRate": round(signed / scheduled * 100, 1) if scheduled else 0,
                        "newCustomers": new_customers, "enrolledCustomers": enrolled_customers,
                        "conversionRate": round(enrolled_customers / new_customers * 100, 1)
                        if new_customers else 0},
            "daily": daily,
            "teachers": teachers,
        }
    finally:
        con.close()
