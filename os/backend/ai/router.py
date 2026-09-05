def route(task_type: str):
    if task_type == "video_generation":
        return "video"
    return "text"
