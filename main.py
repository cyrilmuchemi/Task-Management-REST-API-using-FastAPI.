from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

tasks_db: dict[int, dict] = {}
next_id = 1

class TaskCreate(BaseModel):
    title: str
    description : str | None = None
    completed: bool = False


@app.post("/tasks", status_code = 201)
def create_task(task: TaskCreate):
    global next_id
    task_id = next_id
    next_id += 1
    new_task = {
        "id": task_id,
        "title": task.title,
        "description": task.description,
        "completed": task.completed
    }
    tasks_db[task_id] = new_task

    return new_task

@app.get("/tasks")
def get_tasks():
    return list(tasks_db.values())

@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    task = tasks_db.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found!")
    return task

class TaskUpdate(BaseModel):
    title: str
    description: str | None
    completed: bool

@app.put("/tasks/{task_id}")
def update_task(task_id: int, updated_task: TaskUpdate):
    task = tasks_db.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    task["title"] = updated_task.title
    task["description"] = updated_task.description
    task["completed"] = updated_task.completed
    return task

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    del tasks_db[task_id]
    return{"message": f"Task {task_id} deleted successfully"}

