"""Locust performance test scenarios for the reading tutor API."""

from locust import HttpUser, between, task

from tests.perf.auth_helper import auth_headers, register_and_login


class ParentUser(HttpUser):
    """Simulates a parent managing their account."""

    weight = 1
    wait_time = between(1, 3)

    def on_start(self):
        self.token, self.family_id = register_and_login(self.client)
        self.headers = auth_headers(self.token)

        # Create a child for this family
        resp = self.client.post(
            "/api/children/",
            json={"name": "PerfChild", "avatar": "fox"},
            headers=self.headers,
        )
        if resp.status_code == 201:
            self.child_id = resp.json()["id"]
        else:
            self.child_id = None

    @task(3)
    def list_stories(self):
        self.client.get("/api/stories/", headers=self.headers)

    @task(2)
    def list_children(self):
        self.client.get("/api/children/", headers=self.headers)

    @task(1)
    def get_analytics(self):
        if self.child_id:
            self.client.get(
                f"/api/parent/analytics/{self.child_id}",
                headers=self.headers,
            )

    @task(1)
    def get_all_analytics(self):
        self.client.get("/api/parent/analytics", headers=self.headers)

    @task(1)
    def leaderboard(self):
        self.client.get("/api/children/leaderboard", headers=self.headers)


class ChildReadingUser(HttpUser):
    """Simulates a child reading a story — the most common flow."""

    weight = 3
    wait_time = between(0.5, 2)

    def on_start(self):
        self.token, self.family_id = register_and_login(self.client)
        self.headers = auth_headers(self.token)

        # Create a child
        resp = self.client.post(
            "/api/children/",
            json={"name": "Reader", "avatar": "owl"},
            headers=self.headers,
        )
        self.child_id = resp.json()["id"] if resp.status_code == 201 else None

        # Cache story info
        self.story_id = None
        self.story_words = []
        self._load_story()

    def _load_story(self):
        """Find a ready story to read."""
        resp = self.client.get("/api/stories/", headers=self.headers)
        if resp.status_code == 200:
            stories = resp.json()
            if stories:
                story = stories[0]
                self.story_id = story["id"]
                # Collect word IDs for session completion
                for sent in story.get("sentences", []):
                    for word in sent.get("words", []):
                        self.story_words.append(word["id"])

    @task(3)
    def get_story_detail(self):
        if self.story_id:
            self.client.get(
                f"/api/stories/{self.story_id}",
                headers=self.headers,
            )

    @task(2)
    def get_story_image(self):
        if self.story_id:
            self.client.get(
                f"/api/assets/image/{self.story_id}/0",
                name="/api/assets/image/[story_id]/[idx]",
            )

    @task(2)
    def get_word_audio(self):
        if self.story_id and self.story_words:
            word_id = self.story_words[0]
            self.client.get(
                f"/api/assets/audio/word/{self.story_id}/{word_id}",
                name="/api/assets/audio/word/[story_id]/[word_id]",
            )

    @task(1)
    def get_sentence_audio(self):
        if self.story_id:
            self.client.get(
                f"/api/assets/audio/sentence/{self.story_id}/0",
                name="/api/assets/audio/sentence/[story_id]/[idx]",
            )

    @task(1)
    def create_and_complete_session(self):
        if not self.story_id or not self.child_id or not self.story_words:
            return

        # Create session
        resp = self.client.post(
            "/api/sessions/",
            json={"child_id": self.child_id, "story_id": self.story_id},
            headers=self.headers,
        )
        if resp.status_code != 201:
            return

        session_id = resp.json()["id"]

        # Complete session with results
        results = [
            {"word_id": wid, "attempts": 1, "correct": True}
            for wid in self.story_words[:5]  # Submit first 5 words
        ]
        self.client.post(
            f"/api/sessions/{session_id}/complete",
            json={"results": results},
            headers=self.headers,
            name="/api/sessions/[id]/complete",
        )

    @task(1)
    def list_child_sessions(self):
        if self.child_id:
            self.client.get(
                f"/api/sessions/child/{self.child_id}",
                headers=self.headers,
                name="/api/sessions/child/[child_id]",
            )


class GenerationUser(HttpUser):
    """Simulates story generation — triggers generation and polls status."""

    weight = 1
    wait_time = between(2, 5)

    def on_start(self):
        self.token, self.family_id = register_and_login(self.client)
        self.headers = auth_headers(self.token)
        self.job_ids = []

    @task(2)
    def trigger_generation(self):
        resp = self.client.post(
            "/api/stories/generate",
            json={
                "topic": "a friendly dragon",
                "difficulty": "easy",
                "theme": "adventure",
            },
            headers=self.headers,
        )
        if resp.status_code == 200:
            self.job_ids.append(resp.json()["id"])

    @task(3)
    def poll_job_status(self):
        if self.job_ids:
            job_id = self.job_ids[-1]
            self.client.get(
                f"/api/generation/jobs/{job_id}",
                headers=self.headers,
                name="/api/generation/jobs/[id]",
            )

    @task(1)
    def list_jobs(self):
        self.client.get("/api/generation/jobs", headers=self.headers)

    @task(1)
    def get_job_logs(self):
        if self.job_ids:
            job_id = self.job_ids[-1]
            self.client.get(
                f"/api/generation/jobs/{job_id}/logs",
                headers=self.headers,
                name="/api/generation/jobs/[id]/logs",
            )
