from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from database import get_connection, initialize_database

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield

app = FastAPI(lifespan=lifespan)

def _validate_title_value(value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Title cannot be empty or whitespace only")
        if len(cleaned) < 3:
            raise ValueError("Title must be at least 3 characters long")
        if len(cleaned) > 100:
            raise ValueError("Title must not exceed 100 characters")
        return cleaned



class TaskBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=100)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _validate_title_value(value)

class TaskCreate(TaskBase):
    description: str | None = Field(default=None, max_length=500)
    completed: bool = False


class TaskUpdate(TaskBase):
    description: str | None = Field(..., max_length=500)
    completed: bool


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    completed: bool | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_title_value(value)

class TaskResponse(BaseModel):
    id: int
    title: str
    description: str | None = None
    completed: bool


@app.get("/")
def home():
    return {"message": "Welcome to the Task Management API"}


@app.get("/health")
def healthy():
    return {"status": "healthy"}


@app.post("/tasks", status_code=201, response_model=TaskResponse)
def create_task(task: TaskCreate):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tasks (title, description, completed) VALUES (?, ?, ?)",
            (task.title, task.description, int(task.completed))
        )
        conn.commit()
        created_id = cursor.lastrowid
        cursor.execute(
            "SELECT id, title, description, completed FROM tasks WHERE id = ?",
            (created_id,),
        )
        row = cursor.fetchone()

        if row is None:
            raise HTTPException(status_code=500, detail="Failed to retrieve created task")

        return{
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "completed": bool(int(row["completed"]))
        }
    finally:
        conn.close()


@app.get("/tasks", response_model=list[TaskResponse])
def get_tasks():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, description, completed FROM tasks")
        rows = cursor.fetchall()

        return [
            {
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "completed": bool(row["completed"])
            }
            for row in rows
        ]
    finally:
        conn.close()


@app.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, title, description, completed FROM tasks WHERE id = ?",
            (task_id,),
        )
        row = cursor.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Task not found")

        return {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "completed": bool(row["completed"])
        }
    finally:
        conn.close()


@app.put("/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, updated_task: TaskUpdate):
    task = tasks_db.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    task["title"] = updated_task.title
    task["description"] = updated_task.description
    task["completed"] = updated_task.completed
    return task


@app.patch("/tasks/{task_id}", response_model=TaskResponse)
def patch_task(task_id: int, patch: TaskPatch):
    task = tasks_db.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    updates = patch.model_dump(exclude_unset=True)
    for field, value in updates.items():
        task[field] = value

    return task


@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")

    del tasks_db[task_id]
    return {"message": f"Task {task_id} deleted successfully"}