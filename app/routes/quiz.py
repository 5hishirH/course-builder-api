from pydantic import BaseModel, ConfigDict, model_validator
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.core.database import get_db
from app.models.quiz import Quiz, Question, Option
from sqlalchemy import select
from sqlalchemy.orm import selectinload


class OptionCreate(BaseModel):
    option_text: str
    is_correct: bool = False


class QuestionCreate(BaseModel):
    question_text: str
    marks: int = 1
    options: list[OptionCreate]


    @model_validator(mode="after")
    def validate_correct(self):
        correct = sum(o.is_correct for o in self.options)

        if correct != 1:
            raise ValueError(
                "Question must have exactly one correct option"
            )

        if len(self.options) < 2:
            raise ValueError(
                "Question must have at least 2 options"
            )

        return self


class QuizCreate(BaseModel):
    title: str
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    questions: list[QuestionCreate]

class OptionResponse(BaseModel):
    id: int
    option_text: str
    model_config = ConfigDict(from_attributes=True)

class QuestionResponse(BaseModel):
    id: int
    question_text: str
    marks: int
    options: list[OptionResponse]
    model_config = ConfigDict(from_attributes=True)

class QuizResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    duration_minutes: Optional[int]
    questions: list[QuestionResponse]
    model_config = ConfigDict(from_attributes=True)

router = APIRouter()

@router.post(
    "/api/quizzes",
    response_model=QuizResponse,
    status_code=201
)
async def create_quiz(
    payload: QuizCreate,
    db: AsyncSession = Depends(get_db)
):

    quiz = Quiz(
        title=payload.title.strip(),
        description=payload.description.strip()
        if payload.description else None,
        duration_minutes=payload.duration_minutes
    )

    try:

        for q in payload.questions:
            question = Question(
                question_text=q.question_text.strip(),
                marks=q.marks
            )

            question.options = [
                Option(
                    option_text=o.option_text.strip(),
                    is_correct=o.is_correct
                )
                for o in q.options
            ]

            quiz.questions.append(question)

        db.add(quiz)
        await db.commit()
        stmt = (
            select(Quiz)
            .options(
                selectinload(Quiz.questions)
                .selectinload(Question.options)
            )
            .where(Quiz.id == quiz.id)
        )

        result = await db.execute(stmt)

        quiz = result.scalar_one()

        return quiz

    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Quiz creation failed"
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unexpected error during quiz creation"
        )