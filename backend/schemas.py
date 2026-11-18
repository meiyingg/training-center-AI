from __future__ import annotations

from datetime import date as DateType, time as TimeType
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Role = Literal["admin", "teacher", "student"]


class CleanModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class LoginInput(CleanModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=1, max_length=128)
    remember: bool = False


class RegisterInput(LoginInput):
    password: str = Field(min_length=8, max_length=128)
    remember: bool = False
    name: str = Field(min_length=1, max_length=50)
    phone: str = Field(default="", max_length=20)


class PasswordInput(CleanModel):
    old: str = Field(min_length=1, max_length=128)
    new: str = Field(min_length=8, max_length=128)


class CustomerCreate(CleanModel):
    name: str = Field(min_length=1, max_length=50)
    phone: str
    contact: str = Field(default="电话", max_length=30)
    interest: str = Field(default="", max_length=100)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        if not value.isdigit() or len(value) != 11:
            raise ValueError("手机号须为11位数字")
        return value


class CustomerUpdate(CleanModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    phone: str | None = None
    contact: str | None = Field(default=None, max_length=30)
    interest: str | None = Field(default=None, max_length=100)
    status: Literal["pending", "enrolled"] | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is not None and (not value.isdigit() or len(value) != 11):
            raise ValueError("手机号须为11位数字")
        return value


class FollowupCreate(CleanModel):
    method: Literal["电话", "微信", "面谈", "短信", "其他"] = "电话"
    note: str = Field(min_length=1, max_length=500)
    result: str = Field(default="", max_length=100)
    nextDate: DateType | None = None


class TeacherCreate(CleanModel):
    name: str = Field(min_length=1, max_length=50)
    phone: str = Field(default="", max_length=20)
    subject: str = Field(default="", max_length=100)
    createAccount: bool = False
    username: str = Field(default="", max_length=32)
    password: str = Field(default="", max_length=128)


class TeacherUpdate(CleanModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    phone: str | None = Field(default=None, max_length=20)
    subject: str | None = Field(default=None, max_length=100)


class TeacherAccountCreate(CleanModel):
    username: str = Field(default="", max_length=32)
    password: str = Field(min_length=8, max_length=128)


class StudentCreate(CleanModel):
    name: str = Field(min_length=1, max_length=50)
    phone: str = Field(default="", max_length=20)
    email: str = Field(default="", max_length=100)
    gender: Literal["", "男", "女", "其他"] = ""
    birthDate: DateType | None = None
    school: str = Field(default="", max_length=100)
    grade: str = Field(default="", max_length=50)
    guardianName: str = Field(default="", max_length=50)
    guardianPhone: str = Field(default="", max_length=20)
    address: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=1000)
    status: Literal["active", "inactive"] = "active"
    createAccount: bool = False
    username: str = Field(default="", max_length=32)
    password: str = Field(default="", max_length=128)
    from_: str | None = Field(default=None, alias="from")


class StudentUpdate(CleanModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=100)
    gender: Literal["", "男", "女", "其他"] | None = None
    birthDate: DateType | None = None
    school: str | None = Field(default=None, max_length=100)
    grade: str | None = Field(default=None, max_length=50)
    guardianName: str | None = Field(default=None, max_length=50)
    guardianPhone: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=1000)
    status: Literal["active", "inactive"] | None = None


class StudentAccountCreate(CleanModel):
    username: str = Field(default="", max_length=32)
    password: str = Field(min_length=8, max_length=128)


class CourseCreate(CleanModel):
    date: DateType
    start: TimeType
    end: TimeType
    teacherId: str = Field(min_length=1)
    topic: str = Field(min_length=1, max_length=100)
    location: str = Field(default="", max_length=100)
    studentIds: list[str] = Field(default_factory=list)

    @field_validator("studentIds")
    @classmethod
    def unique_students(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class CourseBatchCreate(CourseCreate):
    repeatWeeks: int = Field(default=1, ge=1, le=52)


class CourseUpdate(CleanModel):
    date: DateType | None = None
    start: TimeType | None = None
    end: TimeType | None = None
    teacherId: str | None = None
    topic: str | None = Field(default=None, min_length=1, max_length=100)
    location: str | None = Field(default=None, max_length=100)
    studentIds: list[str] | None = None


class StudentIdsInput(CleanModel):
    studentIds: list[str] = Field(default_factory=list)


class CheckinInput(CleanModel):
    courseId: str = Field(min_length=1)
    studentId: str | None = None


class UserCreate(CleanModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    role: Role
    name: str = Field(min_length=1, max_length=50)
    phone: str = Field(default="", max_length=20)
    subject: str = Field(default="", max_length=100)
    link_id: str | None = None


class UserRoleInput(CleanModel):
    role: Role


class ResetPasswordInput(CleanModel):
    password: str = Field(min_length=8, max_length=128)
