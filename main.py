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
    conn = get_connection()
    try:
        cursor =  conn.cursor()
        cursor.execute(
            "SELECT id FROM tasks WHERE id = ?",
            (task_id,),
        )

        existing = cursor.fetchone()

        if existing is None:
            raise HTTPException(status_code=404, detail="Task not found")

        cursor.execute(
            """
            UPDATE tasks SET title = ?, description = ?, completed = ? WHERE id = ?
            """,
            (
                updated_task.title,
                updated_task.description,
                int(updated_task.completed),
                task_id,
            ),
        )
        conn.commit()

        cursor.execute(
            "SELECT id, title, description, completed FROM tasks WHERE id = ?",
            (task_id,),
        )

        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=500, detail="Failed to retrieve updated task")

        return{
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "completed": bool(row["completed"])
        }
    finally:
        conn.close()

@app.patch("/tasks/{task_id}", response_model=TaskResponse)
def patch_task(task_id: int, patch: TaskPatch):
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

        updates = patch.model_dump(exclude_unset=True)
        if not updates:
            return{
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "completed": bool(row["completed"])
            }

        set_clauses: list[str] = []
        params: list[object] = []

        for field, value in updates.items():
            if field == "title":
                if value is None:
                    raise HTTPException(status_code=422, detail="Title cannot be null")
                set_clauses.append("title = ?")
                params.append(value)
            elif field == "description":
                set_clauses.append("description = ?")
                params.append(value)
            elif field == "completed":
                if value is None:
                    raise HTTPException(status_code=422, detail="Completed cannot be null")
                set_clauses.append("completed = ?")
                params.append(int(value))

        params.append(task_id)
        sql = f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = ?"
        cursor.execute(sql, tuple(params))
        conn.commit()

        cursor.execute(
            "SELECT id, title, description, completed FROM tasks WHERE id = ?",
            (task_id,),
        )

        updated_row = cursor.fetchone()
        if updated_row is None:
            raise HTTPException(status_code=500, detail="Failed to retrieve updated task")

        return {
            "id": updated_row["id"],
            "title": updated_row["title"],
            "description": updated_row["description"],
            "completed": bool(updated_row["completed"])
        }

    finally:
        conn.close()


@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM tasks WHERE id = ?",
            (task_id,),
        )

        existing = cursor.fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Task not found")

        cursor.execute(
            "DELETE FROM tasks WHERE id = ?",
            (task_id,),
        )
        conn.commit()

        return{"message": f"Task {task_id} deleted successfully"}
    
    finally:
        conn.close()