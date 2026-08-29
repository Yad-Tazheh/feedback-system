we will explain each engineering decisions in this file 
my decisions are in normal font
reviewer decisions and comments are in italic format
----------------

we have an overview of the project as such:
Browser
                       │
                       ▼
              feedback_system/urls.py
                       │
                       ▼
                 feedbacks/urls.py
                       │
                       ▼
                 feedbacks/views.py
                       │
              ┌────────┴────────┐
              ▼                 ▼
        Feedback Model       AIService
              │                 │
              ▼                 ▼
           SQLite          LM Studio API
                                │
                                ▼
                         Qwen2.5-7B
-------------------------------------------
feedback_system = Project / settings.py entire django project settings
feedbacks        = Application



model layer:
Django provides an abstraction layer (the “models”) for structuring and manipulating the data of your web application

view layer:
Django has the concept of “views” to encapsulate the logic responsible for processing a user’s request and for returning the response.

template layer:
The template layer provides a designer-friendly syntax for rendering the information to be presented to the user.

form layer:
Django provides a rich framework to facilitate the creation of forms and the manipulation of form data.





















