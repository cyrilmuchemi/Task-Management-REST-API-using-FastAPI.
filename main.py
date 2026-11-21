from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

app = FastAPI()

tasks_db: dict[int, dict] = {}
next_id = 1


class TaskBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=100)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Title cannot be empty or whitespace only")
        if len(cleaned) < 3:
            raise ValueError("Title must be at least 3 characters long")
        if len(cleaned) > 100:
            raise ValueError("Title must not exceed 100 characters")
        return cleaned


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
    def validate_patch_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Title cannot be empty or have whitespace only")
        if len(cleaned) < 3:
            raise ValueError("Title must be at least 3 characters long")
        if len(cleaned) > 100:
            raise ValueError("Title must not exceed 100 characters")

        return cleaned

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
    global next_id

    task_id = next_id
    next_id += 1

    new_task = {
        "id": task_id,
        "title": task.title,
        "description": task.description,
        "completed": task.completed,
        "internal_notes": "Created via API V1",
        "internal_flag": True
    }
    tasks_db[task_id] = new_task
    return new_task


@app.get("/tasks", response_model=list[TaskResponse])
def get_tasks():
    return list(tasks_db.values())


@app.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int):
    task = tasks_db.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


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