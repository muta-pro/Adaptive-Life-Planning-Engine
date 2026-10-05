"""Each example is one bounded slice, including legitimate recovery work."""

from skrov.domain import Energy, Task


def sample_tasks() -> list[Task]:
    # Return new objects each time; editing one workspace must not affect another.
    return [
        Task(1, "Webserv event loop", "Learning", 25, Energy.HIGH, project="Webserv",
             importance=4, cycle_relevance=5, switching_cost=1),
        Task(2, "CPP Module 08", "Learning", 20, Energy.MEDIUM, project="CPP",
             importance=4, cycle_relevance=4),
        Task(3, "Job application", "Career", 15, Energy.LOW,
             importance=5, cycle_relevance=2),
        Task(4, "Menura landing page", "Projects", 30, Energy.MEDIUM, project="Menura",
             importance=3, cycle_relevance=3, rhythm_target=2, switching_cost=2),
        Task(5, "Climbing / recovery", "Health", 20, Energy.LOW, context="any",
             importance=3, cycle_relevance=2, rhythm_target=3),
    ]
