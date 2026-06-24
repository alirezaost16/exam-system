from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True, index=True)
    username      = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    full_name     = Column(String(100), nullable=False)
    email         = Column(String(100), unique=True, nullable=False)
    role          = Column(String(20), default="student")  # admin / teacher / student
    is_verified   = Column(Boolean, default=True)  # برای استادان: نیاز به تایید ادمین قبل از ورود
    created_at    = Column(DateTime, default=datetime.utcnow)
    sessions      = relationship("UserSession", back_populates="user")
    exams_created = relationship("Exam", back_populates="creator")
    results       = relationship("ExamResult", back_populates="student")

class UserSession(Base):
    __tablename__ = "user_sessions"
    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"))
    token      = Column(String(64), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    user       = relationship("User", back_populates="sessions")

class Exam(Base):
    __tablename__ = "exams"
    id               = Column(Integer, primary_key=True, index=True)
    title            = Column(String(200), nullable=False)
    description      = Column(Text)
    start_time       = Column(DateTime, nullable=False)
    end_time         = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    creator_id       = Column(Integer, ForeignKey("users.id"))
    is_active        = Column(Boolean, default=True)
    is_finalized     = Column(Boolean, default=False)
    created_at       = Column(DateTime, default=datetime.utcnow)
    creator          = relationship("User", back_populates="exams_created")
    questions        = relationship("Question", back_populates="exam")
    results          = relationship("ExamResult", back_populates="exam")

class Question(Base):
    __tablename__ = "questions"
    id             = Column(Integer, primary_key=True, index=True)
    exam_id        = Column(Integer, ForeignKey("exams.id"))
    question_text  = Column(Text, nullable=False)
    question_type  = Column(String(20), default="multiple_choice")  # multiple_choice / descriptive
    points         = Column(Float, default=1.0)
    options        = Column(Text)           # JSON: {"a":.., "b":.., "c":.., "d":..}
    correct_answer = Column(String(10))     # "a" / "b" / "c" / "d"
    time_limit     = Column(Integer, default=0)  # seconds per question, 0 = no limit
    exam           = relationship("Exam", back_populates="questions")

class ExamResult(Base):
    __tablename__ = "exam_results"
    id                 = Column(Integer, primary_key=True, index=True)
    exam_id            = Column(Integer, ForeignKey("exams.id"))
    student_id         = Column(Integer, ForeignKey("users.id"))
    score              = Column(Float, default=0.0)   # auto-graded (MC) + teacher descriptive score
    descriptive_score  = Column(Float, default=0.0)   # نمره تشریحی که استاد وارد می‌کند
    descriptive_graded = Column(Boolean, default=False)  # آیا تشریحی‌ها تصحیح شده‌اند؟
    teacher_comment    = Column(Text, default="")     # نظر کلی استاد
    answers            = Column(Text)                 # JSON
    file_metadata      = Column(Text, default="{}")   # JSON: {qid: [{name, path, mime}]}
    submitted_at       = Column(DateTime)
    started_at         = Column(DateTime, default=datetime.utcnow)
    exam               = relationship("Exam", back_populates="results")
    student            = relationship("User", back_populates="results")
    appeals            = relationship("GradeAppeal", back_populates="result")


class GradeAppeal(Base):
    __tablename__ = "grade_appeals"
    id              = Column(Integer, primary_key=True, index=True)
    result_id       = Column(Integer, ForeignKey("exam_results.id"), nullable=False)
    student_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    appeal_text     = Column(Text, nullable=False)           # متن اعتراض دانشجو
    status          = Column(String(20), default="pending")  # pending / accepted / rejected
    teacher_reply   = Column(Text, default="")               # پاسخ استاد
    old_score       = Column(Float, nullable=True)           # نمره قبل از تغییر
    new_score       = Column(Float, nullable=True)           # نمره بعد از تغییر (در صورت قبول)
    created_at      = Column(DateTime, default=datetime.utcnow)
    reviewed_at     = Column(DateTime, nullable=True)
    result          = relationship("ExamResult", back_populates="appeals")
    student         = relationship("User")
