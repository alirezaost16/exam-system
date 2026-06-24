from fastapi import FastAPI, Request, Depends, HTTPException, Form, status, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, List
import hashlib, secrets, json, os, shutil, mimetypes, re
from pathlib import Path
from database import SessionLocal, engine, Base
import models

# ─── مسیر ذخیره فایل‌های آپلودی ────────────────────────────────────────────
UPLOAD_DIR = Path("uploads/submissions")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

Base.metadata.create_all(bind=engine)

# ─── Migration سبک: افزودن ستون‌های جدید به دیتابیس قبلی (در صورت نیاز) ──────
def _migrate_sqlite_columns():
    """create_all فقط جدول‌های جدید را می‌سازد، نه ستون‌های جدید روی جدول‌های
    قبلاً موجود. این تابع ستون‌های جدید مدل را در صورت نبودن اضافه می‌کند."""
    with engine.connect() as conn:
        existing_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()}
        if "is_verified" not in existing_cols:
            # کاربران از قبل موجود (از جمله استادان قبلی) تایید شده فرض می‌شوند
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT 1")
            conn.commit()

_migrate_sqlite_columns()

app = FastAPI(title="سامانه آزمون آنلاین", version="2.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ─── Dependency ───────────────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def pending_appeals_count_for_teacher(db: Session, teacher_id: int) -> int:
    """تعداد اعتراض‌های در انتظار بررسی برای آزمون‌های یک استاد (برای بج منوی سایدبار)"""
    exam_ids = [e.id for e in db.query(models.Exam.id).filter_by(creator_id=teacher_id).all()]
    if not exam_ids:
        return 0
    return (
        db.query(models.GradeAppeal)
          .join(models.ExamResult, models.GradeAppeal.result_id == models.ExamResult.id)
          .filter(models.ExamResult.exam_id.in_(exam_ids), models.GradeAppeal.status == "pending")
          .count()
    )

# ─── رندر قالب با تزریق خودکار pending_appeals_count برای استاد ──────────────
# این کار باعث می‌شود بج تعداد اعتراض در انتظار، در منوی سایدبار (base.html)
# در تمام صفحاتی که استاد می‌بیند نمایش داده شود، نه فقط در /dashboard
_original_template_response = templates.TemplateResponse

def render(request: Request, name: str, context: dict = None, db: Session = None, **kwargs):
    context = dict(context or {})
    user = context.get("user")
    if user and getattr(user, "role", None) == "teacher" and "pending_appeals_count" not in context:
        _db = db or SessionLocal()
        try:
            context["pending_appeals_count"] = pending_appeals_count_for_teacher(_db, user.id)
        finally:
            if db is None:
                _db.close()
    return _original_template_response(request, name, context, **kwargs)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# ── الگوی بررسی فرمت صحیح ایمیل (برای ثبت‌نام) ──────────────────────────────
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("session_token")
    if not token:
        return None
    session = db.query(models.UserSession).filter_by(token=token).first()
    if not session or session.expires_at < datetime.utcnow():
        return None
    return db.query(models.User).filter_by(id=session.user_id).first()

# ─── Middleware for session ────────────────────────────────────────────────────
from starlette.middleware.sessions import SessionMiddleware
app.add_middleware(SessionMiddleware, secret_key="EXAM_SYSTEM_SECRET_KEY_2024")

# ══════════════════════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return render(request, "index.html")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    info = None
    if request.query_params.get("pending_teacher"):
        info = "ثبت‌نام شما با موفقیت انجام شد. حساب استادی شما در انتظار تایید مدیر سیستم است و پس از تایید می‌توانید وارد شوید."
    return render(request, "login.html", {"error": None, "info": info})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    # ── FIX: حذف خودکار فاصله‌های ابتدا/انتهای نام کاربری و رمز عبور؛
    # اگه کاربر به اشتباه فاصله اضافه تایپ کرده باشه، باعث خطای «نام کاربری
    # یا رمز عبور اشتباه است» نشه.
    username = username.strip()
    password = password.strip()

    user = db.query(models.User).filter_by(username=username).first()
    if not user or user.password_hash != hash_password(password):
        return render(request, "login.html", {"error": "نام کاربری یا رمز عبور وارد شده صحیح نیست. لطفاً دوباره بررسی کنید."})

    if user.role == "teacher" and not user.is_verified:
        return render(request, "login.html", {
            "error": "حساب استادی شما هنوز تایید نشده است. پس از تایید توسط مدیر سیستم می‌توانید وارد شوید."
        })

    token = secrets.token_urlsafe(32)
    session = models.UserSession(user_id=user.id, token=token, expires_at=datetime.utcnow() + timedelta(hours=24))
    db.add(session)
    db.commit()
    
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie("session_token", token, httponly=True, max_age=86400)
    return response

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return render(request, "register.html", {"error": None})

@app.post("/register")
async def register(request: Request, username: str = Form(...), password: str = Form(...),
                   full_name: str = Form(...), email: str = Form(...), role: str = Form(...),
                   db: Session = Depends(get_db)):
    # ── FIX: حذف خودکار فاصله‌های ابتدا/انتهای فیلدها ──────────────────────
    username = username.strip()
    password = password.strip()
    full_name = full_name.strip()
    email = email.strip()

    # ── FIX: بررسی فرمت صحیح ایمیل ─────────────────────────────────────────
    if not EMAIL_RE.match(email):
        return render(request, "register.html", {"error": "آدرس ایمیل وارد شده معتبر نیست. مثال صحیح: name@example.com"})

    # ── FIX: رمز عبور باید حداقل ۸ کاراکتر باشد ────────────────────────────
    if len(password) < 8:
        return render(request, "register.html", {"error": "رمز عبور باید حداقل ۸ کاراکتر داشته باشد. یک رمز قوی‌تر انتخاب کنید."})

    if db.query(models.User).filter_by(username=username).first():
        return render(request, "register.html", {"error": "این نام کاربری قبلاً در سیستم ثبت شده است. نام کاربری دیگری انتخاب کنید."})

    if db.query(models.User).filter_by(email=email).first():
        return render(request, "register.html", {"error": "این ایمیل قبلاً برای یک حساب کاربری دیگر استفاده شده است."})

    # حساب استادان باید پیش از ورود توسط ادمین تایید شود
    is_verified = role != "teacher"

    user = models.User(username=username, password_hash=hash_password(password),
                       full_name=full_name, email=email, role=role, is_verified=is_verified)
    db.add(user)
    db.commit()

    if role == "teacher":
        return RedirectResponse(url="/login?pending_teacher=1", status_code=302)
    return RedirectResponse(url="/login", status_code=302)

@app.get("/logout")
async def logout(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("session_token")
    if token:
        db.query(models.UserSession).filter_by(token=token).delete()
        db.commit()
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("session_token")
    return response

# ══════════════════════════════════════════════════════════════════════════════
#  PROFILE
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return render(request, "profile.html", {"user": user, "success": None, "error": None})

@app.post("/profile")
async def update_profile(request: Request, full_name: str = Form(...), email: str = Form(...),
                          current_password: str = Form(""), new_password: str = Form(""),
                          db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    full_name = full_name.strip()
    email = email.strip()
    current_password = current_password.strip()
    new_password = new_password.strip()

    # Check email uniqueness
    existing = db.query(models.User).filter(models.User.email == email, models.User.id != user.id).first()
    if existing:
        return render(request, "profile.html", {"user": user,
                                           "error": "این آدرس ایمیل متعلق به حساب کاربری دیگری است. یک ایمیل دیگر وارد کنید.", "success": None})

    user.full_name = full_name
    user.email = email

    if new_password:
        if not current_password or user.password_hash != hash_password(current_password):
            return render(request, "profile.html", {"user": user,
                                               "error": "رمز عبور فعلی که وارد کردید صحیح نیست. دوباره امتحان کنید.", "success": None})
        if len(new_password) < 4:
            return render(request, "profile.html", {"user": user,
                                               "error": "رمز عبور جدید باید حداقل ۴ کاراکتر داشته باشد.", "success": None})
        # ── FIX: اطمینان از اینکه تغییر رمز واقعاً روی همین رکورد دیتابیس اعمال و ذخیره می‌شود ──
        new_hash = hash_password(new_password)
        user.password_hash = new_hash
        db.add(user)

    db.commit()
    db.refresh(user)
    return render(request, "profile.html", {"user": user,
                                       "success": "پروفایل شما با موفقیت به‌روز شد ✨", "error": None})

# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    now = datetime.utcnow()
    if user.role == "student":
        all_results = db.query(models.ExamResult).filter_by(student_id=user.id).all()
        # Only show submitted results in stats/history
        my_results = [r for r in all_results if r.submitted_at]
        submitted_exam_ids = {r.exam_id for r in my_results}
        # In-progress exams (started but not submitted) - still show them as active
        inprogress_exam_ids = {r.exam_id for r in all_results if not r.submitted_at}
        active_exams = db.query(models.Exam).filter(
            models.Exam.start_time <= now, models.Exam.end_time >= now,
            models.Exam.is_active == True, models.Exam.is_finalized == True
        ).all()
        # Remove fully submitted ones; keep in-progress ones visible
        active_exams = [e for e in active_exams if e.id not in submitted_exam_ids]
        return render(request, "dashboard_student.html", {
            "user": user,
            "active_exams": active_exams, "my_results": my_results,
            "inprogress_exam_ids": inprogress_exam_ids
        })
    elif user.role == "teacher":
        my_exams = db.query(models.Exam).filter_by(creator_id=user.id).all()
        pending_appeals_count = pending_appeals_count_for_teacher(db, user.id)

        return render(request, "dashboard_teacher.html", {
            "user": user, "my_exams": my_exams,
            "pending_appeals_count": pending_appeals_count,
        }, db=db)
    else:  # admin
        all_users = db.query(models.User).all()
        all_exams = db.query(models.Exam).all()
        return render(request, "dashboard_admin.html", {
            "user": user,
            "all_users": all_users, "all_exams": all_exams
        })

# ══════════════════════════════════════════════════════════════════════════════
#  EXAM MANAGEMENT (Teacher)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/exams/create", response_class=HTMLResponse)
async def create_exam_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role not in ["teacher", "admin"]:
        return RedirectResponse(url="/login", status_code=302)
    return render(request, "exam_create.html", {"user": user, "error": None})

@app.post("/exams/create")
async def create_exam(request: Request, title: str = Form(...), description: str = Form(""),
                      start_time: str = Form(...), end_time: str = Form(...),
                      duration_minutes: int = Form(...), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role not in ["teacher", "admin"]:
        return RedirectResponse(url="/login", status_code=302)
    
    exam = models.Exam(
        title=title, description=description,
        start_time=datetime.fromisoformat(start_time),
        end_time=datetime.fromisoformat(end_time),
        duration_minutes=duration_minutes,
        creator_id=user.id, is_active=True, is_finalized=False
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return RedirectResponse(url=f"/exams/{exam.id}/questions", status_code=302)

@app.get("/exams/{exam_id}/edit", response_class=HTMLResponse)
async def edit_exam_page(request: Request, exam_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role not in ["teacher", "admin"]:
        return RedirectResponse(url="/login", status_code=302)
    exam = db.query(models.Exam).filter_by(id=exam_id, creator_id=user.id).first()
    if not exam:
        raise HTTPException(status_code=404)
    return render(request, "exam_edit.html", {"user": user, "exam": exam, "error": None})

@app.post("/exams/{exam_id}/edit")
async def edit_exam(request: Request, exam_id: int, title: str = Form(...), description: str = Form(""),
                    start_time: str = Form(...), end_time: str = Form(...),
                    duration_minutes: int = Form(...), db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role not in ["teacher", "admin"]:
        return RedirectResponse(url="/login", status_code=302)
    exam = db.query(models.Exam).filter_by(id=exam_id, creator_id=user.id).first()
    if not exam:
        raise HTTPException(status_code=404)
    exam.title = title
    exam.description = description
    exam.start_time = datetime.fromisoformat(start_time)
    exam.end_time = datetime.fromisoformat(end_time)
    exam.duration_minutes = duration_minutes
    db.commit()
    return RedirectResponse(url=f"/exams/{exam_id}/questions", status_code=302)

@app.post("/exams/{exam_id}/delete")
async def delete_exam(request: Request, exam_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role not in ["teacher", "admin"]:
        return RedirectResponse(url="/login", status_code=302)
    exam = db.query(models.Exam).filter_by(id=exam_id, creator_id=user.id).first()
    if not exam:
        raise HTTPException(status_code=404)
    db.query(models.Question).filter_by(exam_id=exam_id).delete()
    db.query(models.ExamResult).filter_by(exam_id=exam_id).delete()
    db.delete(exam)
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=302)

@app.post("/exams/{exam_id}/finalize")
async def finalize_exam(request: Request, exam_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role not in ["teacher", "admin"]:
        return RedirectResponse(url="/login", status_code=302)
    exam = db.query(models.Exam).filter_by(id=exam_id, creator_id=user.id).first()
    if not exam:
        raise HTTPException(status_code=404)
    exam.is_finalized = True
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=302)

@app.get("/exams/{exam_id}/questions", response_class=HTMLResponse)
async def manage_questions(request: Request, exam_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role not in ["teacher", "admin"]:
        return RedirectResponse(url="/login", status_code=302)
    exam = db.query(models.Exam).filter_by(id=exam_id, creator_id=user.id).first()
    if not exam:
        raise HTTPException(status_code=404)
    questions = db.query(models.Question).filter_by(exam_id=exam_id).all()
    for q in questions:
        q.options_parsed = json.loads(q.options) if q.options else None
    return render(request, "exam_questions.html", {
        "user": user, "exam": exam, "questions": questions
    })

@app.post("/exams/{exam_id}/questions/add")
async def add_question(request: Request, exam_id: int,
                       question_text: str = Form(...), question_type: str = Form(...),
                       points: float = Form(...), option_a: str = Form(""), option_b: str = Form(""),
                       option_c: str = Form(""), option_d: str = Form(""), correct_answer: str = Form(""),
                       time_limit: int = Form(0),
                       db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role not in ["teacher", "admin"]:
        return RedirectResponse(url="/login", status_code=302)
    
    options = None
    if question_type == "multiple_choice":
        options = json.dumps({"a": option_a, "b": option_b, "c": option_c, "d": option_d})
    
    q = models.Question(exam_id=exam_id, question_text=question_text, question_type=question_type,
                        points=points, options=options, correct_answer=correct_answer,
                        time_limit=time_limit)
    db.add(q)
    db.commit()
    return RedirectResponse(url=f"/exams/{exam_id}/questions", status_code=302)

@app.post("/questions/{question_id}/delete")
async def delete_question(request: Request, question_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role not in ["teacher", "admin"]:
        return RedirectResponse(url="/login", status_code=302)
    q = db.query(models.Question).filter_by(id=question_id).first()
    if not q:
        raise HTTPException(status_code=404)
    exam_id = q.exam_id
    # Verify ownership
    exam = db.query(models.Exam).filter_by(id=exam_id, creator_id=user.id).first()
    if not exam:
        raise HTTPException(status_code=403)
    db.delete(q)
    db.commit()
    return RedirectResponse(url=f"/exams/{exam_id}/questions", status_code=302)

# ══════════════════════════════════════════════════════════════════════════════
#  EXAM RESULTS FOR TEACHER
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/exams/{exam_id}/results", response_class=HTMLResponse)
async def exam_results_teacher(request: Request, exam_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role not in ["teacher", "admin"]:
        return RedirectResponse(url="/login", status_code=302)
    exam = db.query(models.Exam).filter_by(id=exam_id, creator_id=user.id).first()
    if not exam:
        raise HTTPException(status_code=404)
    results = db.query(models.ExamResult).filter_by(exam_id=exam_id).all()
    questions = db.query(models.Question).filter_by(exam_id=exam_id).all()
    total_points = sum(q.points for q in questions)
    has_descriptive = any(q.question_type == "descriptive" for q in questions)

    results_data = []
    for r in results:
        student = db.query(models.User).filter_by(id=r.student_id).first()
        status_label = "شرکت کرده" if r.submitted_at else "در حال انجام"
        score_status = ""
        if r.submitted_at and total_points > 0:
            pct = r.score / total_points * 100
            if pct >= 60:
                score_status = "قبول"
            else:
                score_status = "مردود"

        # محاسبه نمره تستی
        answers = {}
        if r.answers:
            try:
                answers = {k: v for k, v in json.loads(r.answers).items() if not k.startswith("desc_score_")}
            except Exception:
                pass
        mc_score = 0.0
        for q in questions:
            if q.question_type == "multiple_choice":
                ans = answers.get(str(q.id), "").strip().lower()
                if ans and ans == (q.correct_answer or "").strip().lower():
                    mc_score += q.points

        # اعتراض‌های این نتیجه
        r_appeals = db.query(models.GradeAppeal).filter_by(result_id=r.id).order_by(models.GradeAppeal.created_at.desc()).all()
        results_data.append({
            "result": r,
            "student": student,
            "status_label": status_label,
            "score_status": score_status,
            "total_points": total_points,
            "mc_score": mc_score,
            "has_descriptive": has_descriptive,
            "appeals": r_appeals,
            "pending_appeal": any(a.status == "pending" for a in r_appeals),
        })

    # جمع کل اعتراض‌های در انتظار
    pending_appeals_count = sum(1 for item in results_data if item["pending_appeal"])

    # لیست مسطح اعتراض‌های این آزمون برای بخش ویژه اعتراضات
    exam_appeals = []
    for item in results_data:
        for ap in item["appeals"]:
            exam_appeals.append({"appeal": ap, "student": item["student"]})
    exam_appeals.sort(key=lambda x: x["appeal"].created_at or datetime.min, reverse=True)

    return render(request, "exam_results_teacher.html", {
        "user": user, "exam": exam,
        "results_data": results_data, "total_points": total_points,
        "has_descriptive": has_descriptive,
        "pending_appeals_count": pending_appeals_count,
        "exam_appeals": exam_appeals,
    })

# ══════════════════════════════════════════════════════════════════════════════
#  TAKE EXAM (Student)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/exams/{exam_id}/take", response_class=HTMLResponse)
async def take_exam_page(request: Request, exam_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != "student":
        return RedirectResponse(url="/login", status_code=302)
    
    exam = db.query(models.Exam).filter_by(id=exam_id, is_active=True).first()
    if not exam:
        raise HTTPException(status_code=404)
    
    now = datetime.utcnow()
    if now < exam.start_time or now > exam.end_time:
        return render(request, "exam_closed.html", {"user": user, "exam": exam})
    
    existing = db.query(models.ExamResult).filter_by(exam_id=exam_id, student_id=user.id).first()
    if existing and existing.submitted_at:
        return RedirectResponse(url=f"/results/{existing.id}", status_code=302)

    if not existing:
        # Brand new attempt — create fresh record
        existing = models.ExamResult(exam_id=exam_id, student_id=user.id, started_at=now, answers="{}")
        db.add(existing)
        db.commit()
        db.refresh(existing)
    else:
        # ── FIX: Resume logic ─────────────────────────────────────────────
        # If the in-progress record's deadline has already expired (e.g. stale record
        # from a previous DB or session), reset the timer so student can actually take exam
        stale_deadline = existing.started_at + timedelta(minutes=exam.duration_minutes)
        if stale_deadline <= now:
            existing.started_at = now
            existing.answers = "{}"   # clear any corrupt/empty answers
            db.commit()

    personal_deadline = min(existing.started_at + timedelta(minutes=exam.duration_minutes), exam.end_time)

    questions = db.query(models.Question).filter_by(exam_id=exam_id).all()
    for q in questions:
        q.options_parsed = json.loads(q.options) if q.options else None
    
    return render(request, "exam_take.html", {
        "user": user, "exam": exam, "questions": questions,
        "personal_deadline": personal_deadline
    })

@app.post("/exams/{exam_id}/submit")
async def submit_exam(request: Request, exam_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != "student":
        return RedirectResponse(url="/login", status_code=302)

    result = db.query(models.ExamResult).filter_by(exam_id=exam_id, student_id=user.id).first()

    if result and result.submitted_at:
        return RedirectResponse(url=f"/results/{result.id}", status_code=302)

    # ── FIX: وقتی دانشجو هیچ پاسخی ثبت نکرده باشه، بدنه‌ی multipart/form-data
    # ممکنه کاملاً خالی برسه (حتی یک فیلد هم نداشته باشه). پارسر چندبخشی در این
    # حالت خطا می‌دهد و این خطا قبلاً به شکل {"detail":"Method Not Allowed"}
    # به کاربر نمایش داده می‌شد و هیچ نتیجه‌ای هم ثبت نمی‌شد. این‌جا آن حالت را
    # می‌گیریم و آن را معادل «بدون پاسخ» در نظر می‌گیریم تا ثبت آزمون ادامه پیدا کند.
    try:
        form_data = await request.form()
    except Exception:
        form_data = {}

    exam = db.query(models.Exam).filter_by(id=exam_id).first()
    if not exam:
        raise HTTPException(status_code=404)
    questions = db.query(models.Question).filter_by(exam_id=exam_id).all()

    total_score = 0.0
    answers_detail = {}

    for q in questions:
        answer = str(form_data.get(f"q_{q.id}", "")).strip()
        answers_detail[str(q.id)] = answer
        if (q.question_type == "multiple_choice"
                and answer
                and answer.lower() == (q.correct_answer or "").strip().lower()):
            total_score += q.points

    if not result:
        result = models.ExamResult(exam_id=exam_id, student_id=user.id, started_at=datetime.utcnow())
        db.add(result)
        db.flush()

    # ─── پردازش فایل‌های آپلودی ───────────────────────────────────────────
    file_meta = {}
    desc_questions = [q for q in questions if q.question_type == "descriptive"]

    for q in desc_questions:
        count_raw = form_data.get(f"file_count_{q.id}", "0")
        try:
            count = int(count_raw)
        except (ValueError, TypeError):
            count = 0

        q_files = []
        for i in range(count):
            field_name = f"file_{q.id}_{i}"
            uploaded = form_data.get(field_name)
            if uploaded is None or not hasattr(uploaded, 'filename'):
                continue
            if not uploaded.filename:
                continue

            # ساخت مسیر امن
            safe_name = f"{result.id}_{q.id}_{i}_{uploaded.filename.replace(' ', '_')}"
            save_path = UPLOAD_DIR / safe_name
            contents = await uploaded.read()

            # محدودیت حجم ۱۰ مگابایت
            if len(contents) > 10 * 1024 * 1024:
                continue

            with open(save_path, "wb") as f:
                f.write(contents)

            mime = uploaded.content_type or mimetypes.guess_type(uploaded.filename)[0] or "application/octet-stream"
            q_files.append({
                "name": uploaded.filename,
                "path": str(save_path),
                "mime": mime,
                "size": len(contents)
            })

        if q_files:
            file_meta[str(q.id)] = q_files

    result.score = total_score
    result.answers = json.dumps(answers_detail, ensure_ascii=False)
    result.file_metadata = json.dumps(file_meta, ensure_ascii=False)
    result.submitted_at = datetime.utcnow()
    db.commit()
    db.refresh(result)
    return RedirectResponse(url=f"/results/{result.id}", status_code=302)


# ── نمایش / دانلود فایل آپلودی (برای استاد) ──────────────────────────────────
@app.get("/submissions/file/{result_id}/{question_id}/{file_index}")
async def get_submission_file(
    request: Request, result_id: int, question_id: int, file_index: int,
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user or user.role not in ["teacher", "admin"]:
        raise HTTPException(status_code=403)

    result = db.query(models.ExamResult).filter_by(id=result_id).first()
    if not result:
        raise HTTPException(status_code=404)

    exam = db.query(models.Exam).filter_by(id=result.exam_id, creator_id=user.id).first()
    if not exam:
        raise HTTPException(status_code=403)

    try:
        meta = json.loads(result.file_metadata or "{}")
        files = meta.get(str(question_id), [])
        if file_index >= len(files):
            raise HTTPException(status_code=404)
        file_info = files[file_index]
        file_path = Path(file_info["path"])
        if not file_path.exists():
            raise HTTPException(status_code=404)
        return FileResponse(
            path=str(file_path),
            media_type=file_info.get("mime", "application/octet-stream"),
            filename=file_info.get("name", "file"),
            headers={"Content-Disposition": f'inline; filename="{file_info.get("name", "file")}"'}
        )
    except (json.JSONDecodeError, KeyError, IndexError):
        raise HTTPException(status_code=404)


# ══════════════════════════════════════════════════════════════════════════════
#  DESCRIPTIVE GRADING (Teacher)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/results/{result_id}/grade", response_class=HTMLResponse)
async def grade_descriptive_page(request: Request, result_id: int, db: Session = Depends(get_db)):
    """صفحه تصحیح سوالات تشریحی توسط استاد"""
    user = get_current_user(request, db)
    if not user or user.role not in ["teacher", "admin"]:
        return RedirectResponse(url="/login", status_code=302)

    result = db.query(models.ExamResult).filter_by(id=result_id).first()
    if not result:
        raise HTTPException(status_code=404)

    exam = db.query(models.Exam).filter_by(id=result.exam_id, creator_id=user.id).first()
    if not exam:
        raise HTTPException(status_code=403, detail="دسترسی غیرمجاز")

    student = db.query(models.User).filter_by(id=result.student_id).first()
    questions = db.query(models.Question).filter_by(exam_id=result.exam_id).all()
    answers = json.loads(result.answers) if result.answers else {}

    # نمره‌های تشریحی موجود (در صورت وجود)
    descriptive_scores = {}
    if result.answers:
        try:
            all_answers = json.loads(result.answers)
            for k, v in all_answers.items():
                if k.startswith("desc_score_"):
                    descriptive_scores[k.replace("desc_score_", "")] = v
        except Exception:
            pass

    descriptive_questions = [q for q in questions if q.question_type == "descriptive"]
    mc_questions = [q for q in questions if q.question_type == "multiple_choice"]
    mc_score = sum(q.points for q in mc_questions if answers.get(str(q.id), "").strip().lower() == (q.correct_answer or "").strip().lower())
    total_points = sum(q.points for q in questions)

    for q in questions:
        q.options_parsed = json.loads(q.options) if q.options else None
        q.student_answer = answers.get(str(q.id), "")
        q.is_correct = (q.student_answer.strip().lower() == (q.correct_answer or "").strip().lower()) if q.question_type == "multiple_choice" else None
        q.given_score = descriptive_scores.get(str(q.id), "")
        # فایل‌های آپلودی دانشجو برای این سوال
        try:
            all_file_meta = json.loads(result.file_metadata or "{}")
        except Exception:
            all_file_meta = {}
        q.uploaded_files = all_file_meta.get(str(q.id), [])

    return render(request, "grade_descriptive.html", {
        "user": user, "result": result, "exam": exam, "student": student,
        "questions": questions, "descriptive_questions": descriptive_questions,
        "total_points": total_points, "mc_score": mc_score,
        "descriptive_scores": descriptive_scores,
    })


@app.post("/results/{result_id}/grade")
async def save_descriptive_grades(request: Request, result_id: int, db: Session = Depends(get_db)):
    """ذخیره نمرات تشریحی و اعمال به نمره کل"""
    user = get_current_user(request, db)
    if not user or user.role not in ["teacher", "admin"]:
        return RedirectResponse(url="/login", status_code=302)

    result = db.query(models.ExamResult).filter_by(id=result_id).first()
    if not result:
        raise HTTPException(status_code=404)

    exam = db.query(models.Exam).filter_by(id=result.exam_id, creator_id=user.id).first()
    if not exam:
        raise HTTPException(status_code=403)

    form_data = await request.form()
    questions = db.query(models.Question).filter_by(exam_id=result.exam_id).all()
    answers = json.loads(result.answers) if result.answers else {}

    # محاسبه مجدد نمره تستی
    mc_score = 0.0
    for q in questions:
        if q.question_type == "multiple_choice":
            ans = answers.get(str(q.id), "").strip().lower()
            if ans and ans == (q.correct_answer or "").strip().lower():
                mc_score += q.points

    # جمع‌آوری نمرات تشریحی از فرم
    descriptive_total = 0.0
    for q in questions:
        if q.question_type == "descriptive":
            raw = form_data.get(f"desc_score_{q.id}", "").strip()
            try:
                given = float(raw)
                given = max(0.0, min(given, q.points))  # کلمپ بین ۰ و حداکثر نمره سوال
            except (ValueError, TypeError):
                given = 0.0
            answers[f"desc_score_{q.id}"] = given
            descriptive_total += given

    teacher_comment = form_data.get("teacher_comment", "").strip()

    result.descriptive_score = descriptive_total
    result.descriptive_graded = True
    result.teacher_comment = teacher_comment
    result.score = mc_score + descriptive_total
    result.answers = json.dumps(answers, ensure_ascii=False)
    db.commit()

    return RedirectResponse(url=f"/exams/{exam.id}/results?graded=1", status_code=302)


# ══════════════════════════════════════════════════════════════════════════════
#  RESULTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/results/{result_id}", response_class=HTMLResponse)
async def view_result(request: Request, result_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    result = db.query(models.ExamResult).filter_by(id=result_id).first()
    if not result:
        raise HTTPException(status_code=404)
    if user.role == "student" and result.student_id != user.id:
        raise HTTPException(status_code=403)
    
    exam = db.query(models.Exam).filter_by(id=result.exam_id).first()
    questions = db.query(models.Question).filter_by(exam_id=result.exam_id).all()
    answers = json.loads(result.answers) if result.answers else {}
    total_points = sum(q.points for q in questions)

    for q in questions:
        q.options_parsed = json.loads(q.options) if q.options else None
        q.student_answer = answers.get(str(q.id), "")
        q.is_correct = (q.student_answer.strip().lower() == (q.correct_answer or "").strip().lower()) if q.question_type == "multiple_choice" else None
        # نمره تشریحی که استاد داده
        q.given_descriptive_score = answers.get(f"desc_score_{q.id}", None)

    has_descriptive = any(q.question_type == "descriptive" for q in questions)
    appeals = db.query(models.GradeAppeal).filter_by(result_id=result_id).order_by(models.GradeAppeal.created_at.desc()).all()
    appeal_pending = any(a.status == "pending" for a in appeals)

    return render(request, "result_view.html", {
        "user": user, "result": result,
        "exam": exam, "questions": questions, "total_points": total_points,
        "has_descriptive": has_descriptive,
        "appeals": appeals, "appeal_pending": appeal_pending,
    })

# ══════════════════════════════════════════════════════════════════════════════
#  GRADE APPEALS (اعتراض به نمره)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/appeals", response_class=HTMLResponse)
async def appeals_page(request: Request, db: Session = Depends(get_db)):
    """صفحه مستقل اعتراضات برای استاد — جدا از داشبورد اصلی"""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if user.role != "teacher":
        raise HTTPException(status_code=403)

    my_exam_ids = [e.id for e in db.query(models.Exam.id).filter_by(creator_id=user.id).all()]
    appeals = []
    if my_exam_ids:
        appeals = (
            db.query(models.GradeAppeal)
              .join(models.ExamResult, models.GradeAppeal.result_id == models.ExamResult.id)
              .filter(models.ExamResult.exam_id.in_(my_exam_ids))
              .order_by(models.GradeAppeal.created_at.desc())
              .all()
        )
    pending_appeals_count = sum(1 for a in appeals if a.status == "pending")

    return render(request, "appeals.html", {
        "user": user,
        "appeals": appeals,
        "pending_appeals_count": pending_appeals_count,
    }, db=db)


@app.post("/results/{result_id}/appeal")
async def submit_appeal(request: Request, result_id: int, db: Session = Depends(get_db)):
    """ثبت اعتراض دانشجو به نمره"""
    user = get_current_user(request, db)
    if not user or user.role != "student":
        return RedirectResponse(url="/login", status_code=302)

    result = db.query(models.ExamResult).filter_by(id=result_id, student_id=user.id).first()
    if not result or not result.submitted_at:
        raise HTTPException(status_code=404)

    # فقط یک اعتراض فعال (pending) در هر نتیجه مجاز است
    existing = db.query(models.GradeAppeal).filter_by(result_id=result_id, status="pending").first()
    if existing:
        return RedirectResponse(url=f"/results/{result_id}?appeal_error=duplicate", status_code=302)

    form_data = await request.form()
    appeal_text = form_data.get("appeal_text", "").strip()
    if not appeal_text or len(appeal_text) < 10:
        return RedirectResponse(url=f"/results/{result_id}?appeal_error=short", status_code=302)

    appeal = models.GradeAppeal(
        result_id=result_id,
        student_id=user.id,
        appeal_text=appeal_text,
        old_score=result.score,
        status="pending",
    )
    db.add(appeal)
    db.commit()
    return RedirectResponse(url=f"/results/{result_id}?appeal_sent=1", status_code=302)


@app.post("/appeals/{appeal_id}/review")
async def review_appeal(request: Request, appeal_id: int, db: Session = Depends(get_db)):
    """بررسی و پاسخ استاد به اعتراض"""
    user = get_current_user(request, db)
    if not user or user.role not in ["teacher", "admin"]:
        return RedirectResponse(url="/login", status_code=302)

    appeal = db.query(models.GradeAppeal).filter_by(id=appeal_id).first()
    if not appeal:
        raise HTTPException(status_code=404)

    result = db.query(models.ExamResult).filter_by(id=appeal.result_id).first()
    exam = db.query(models.Exam).filter_by(id=result.exam_id, creator_id=user.id).first()
    if not exam:
        raise HTTPException(status_code=403)

    form_data = await request.form()
    decision = form_data.get("decision", "rejected")  # accepted / rejected
    teacher_reply = form_data.get("teacher_reply", "").strip()
    new_score_raw = form_data.get("new_score", "").strip()

    appeal.status = decision
    appeal.teacher_reply = teacher_reply
    appeal.reviewed_at = datetime.utcnow()

    if decision == "accepted" and new_score_raw:
        try:
            new_score = float(new_score_raw)
            total_points = sum(q.points for q in db.query(models.Question).filter_by(exam_id=result.exam_id).all())
            new_score = max(0.0, min(new_score, total_points))
            appeal.new_score = new_score
            result.score = new_score
        except (ValueError, TypeError):
            pass

    db.commit()

    # برگشت به همان صفحه‌ای که فرم از آن ارسال شده (داشبورد یا صفحه نتایج آزمون)
    redirect_to = form_data.get("redirect_to", "").strip()
    target = redirect_to if redirect_to.startswith("/") else f"/exams/{exam.id}/results"
    sep = "&" if "?" in target else "?"
    return RedirectResponse(url=f"{target}{sep}appeal_reviewed=1", status_code=302)


@app.get("/transcript", response_class=HTMLResponse)
async def transcript(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role != "student":
        return RedirectResponse(url="/login", status_code=302)
    results = db.query(models.ExamResult).filter_by(student_id=user.id).all()
    for r in results:
        r.exam = db.query(models.Exam).filter_by(id=r.exam_id).first()
    return render(request, "transcript.html", {"user": user, "results": results})

# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/admin/users/{user_id}/role")
async def change_role(request: Request, user_id: int, role: str = Form(...), db: Session = Depends(get_db)):
    current = get_current_user(request, db)
    if not current or current.role != "admin":
        raise HTTPException(status_code=403)
    u = db.query(models.User).filter_by(id=user_id).first()
    if u:
        u.role = role
        db.commit()
    return RedirectResponse(url="/dashboard", status_code=302)

@app.post("/admin/users/{user_id}/delete")
async def delete_user(request: Request, user_id: int, db: Session = Depends(get_db)):
    current = get_current_user(request, db)
    if not current or current.role != "admin":
        raise HTTPException(status_code=403)
    db.query(models.User).filter_by(id=user_id).delete()
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=302)

@app.post("/admin/users/{user_id}/verify")
async def verify_teacher(request: Request, user_id: int, db: Session = Depends(get_db)):
    """تایید حساب استاد توسط ادمین تا امکان ورود را داشته باشد"""
    current = get_current_user(request, db)
    if not current or current.role != "admin":
        raise HTTPException(status_code=403)
    u = db.query(models.User).filter_by(id=user_id).first()
    if u:
        u.is_verified = True
        db.commit()
    return RedirectResponse(url="/dashboard", status_code=302)

@app.get("/admin/users/{user_id}/edit", response_class=HTMLResponse)
async def edit_user_page(request: Request, user_id: int, db: Session = Depends(get_db)):
    """صفحه ویرایش کامل اطلاعات یک کاربر توسط ادمین"""
    current = get_current_user(request, db)
    if not current or current.role != "admin":
        return RedirectResponse(url="/login", status_code=302)
    target_user = db.query(models.User).filter_by(id=user_id).first()
    if not target_user:
        raise HTTPException(status_code=404)
    return render(request, "user_edit.html", {
        "user": current, "target_user": target_user, "error": None, "success": None
    })

@app.post("/admin/users/{user_id}/edit")
async def edit_user(request: Request, user_id: int,
                    username: str = Form(...), full_name: str = Form(...), email: str = Form(...),
                    role: str = Form(...), is_verified: str = Form(""), new_password: str = Form(""),
                    db: Session = Depends(get_db)):
    """ویرایش اطلاعات هر کاربر توسط ادمین (نام، ایمیل، نام کاربری، نقش، تایید، بازنشانی رمز)"""
    current = get_current_user(request, db)
    if not current or current.role != "admin":
        return RedirectResponse(url="/login", status_code=302)
    target_user = db.query(models.User).filter_by(id=user_id).first()
    if not target_user:
        raise HTTPException(status_code=404)

    username = username.strip()
    full_name = full_name.strip()
    email = email.strip()

    # یکتا بودن نام کاربری و ایمیل (به‌جز خود همین کاربر)
    dup_username = db.query(models.User).filter(models.User.username == username, models.User.id != user_id).first()
    if dup_username:
        return render(request, "user_edit.html", {
            "user": current, "target_user": target_user,
            "error": "این نام کاربری متعلق به کاربر دیگری است. نام کاربری دیگری انتخاب کنید.", "success": None
        })
    dup_email = db.query(models.User).filter(models.User.email == email, models.User.id != user_id).first()
    if dup_email:
        return render(request, "user_edit.html", {
            "user": current, "target_user": target_user,
            "error": "این آدرس ایمیل در سیستم برای کاربر دیگری ثبت شده است.", "success": None
        })

    target_user.username = username
    target_user.full_name = full_name
    target_user.email = email
    target_user.role = role
    target_user.is_verified = bool(is_verified)

    new_password = new_password.strip()
    if new_password:
        target_user.password_hash = hash_password(new_password)

    db.commit()
    db.refresh(target_user)
    return render(request, "user_edit.html", {
        "user": current, "target_user": target_user,
        "error": None, "success": "اطلاعات کاربر با موفقیت به‌روز شد ✅"
    })

# ─── Seed initial admin ───────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    db = SessionLocal()
    try:
        if not db.query(models.User).filter_by(username="admin").first():
            admin = models.User(username="admin", password_hash=hash_password("admin123"),
                                full_name="مدیر سیستم", email="admin@exam.ir", role="admin")
            db.add(admin)
            teacher = models.User(username="teacher1", password_hash=hash_password("teacher123"),
                                  full_name="استاد نمونه", email="teacher@exam.ir", role="teacher")
            db.add(teacher)
            student = models.User(username="student1", password_hash=hash_password("student123"),
                                  full_name="دانشجو نمونه", email="student@exam.ir", role="student")
            db.add(student)
            db.commit()
    finally:
        db.close()


@app.post("/admin/exams/{exam_id}/clear-inprogress")
async def clear_inprogress(request: Request, exam_id: int, db: Session = Depends(get_db)):
    """Admin: remove stale in-progress (not submitted) exam results."""
    current = get_current_user(request, db)
    if not current or current.role not in ["admin", "teacher"]:
        raise HTTPException(status_code=403)
    deleted = db.query(models.ExamResult).filter(
        models.ExamResult.exam_id == exam_id,
        models.ExamResult.submitted_at == None
    ).delete()
    db.commit()
    return {"deleted": deleted}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
