def calculate_score(performance):
    views = performance.get('views', 0)
    likes = performance.get('likes', 0)
    shares = performance.get('shares', 0)
    watch_time = performance.get('watch_time', 0)

    score = 0
    if views > 1000:
        score += 25
    if likes > 100:
        score += 25
    if shares > 20:
        score += 25
    if watch_time > 300:
        score += 25

    return min(score, 100)
