"""Remembered moments: the chat shows a past message only when the reply drew on it."""

from app.services.conversation_craft import moments_used, recalled_moments


def _recall(*said):
    recalled_moments.set(tuple({"said": s, "when": "3 days ago", "conversation_id": "c1"} for s in said))


def test_a_reply_that_brings_back_an_old_detail_shows_it():
    _recall("my physics internship interview is on friday and i'm nervous")
    used = moments_used("wait, wasn't the internship interview this week? how did it go", "ugh long day")
    assert [m["when"] for m in used] == ["3 days ago"]
    assert used[0]["said"].startswith("my physics internship")


def test_words_they_just_said_dont_count_as_remembering():
    _recall("my physics internship interview is on friday and i'm nervous")
    used = moments_used("an internship interview sounds stressful", "i have an internship interview soon")
    assert used == []


def test_a_reply_that_ignores_the_memory_shows_nothing():
    _recall("my physics internship interview is on friday and i'm nervous")
    assert moments_used("haha same, what are you eating tonight", "so hungry") == []


def test_no_more_than_two_and_no_repeats():
    _recall(
        "started learning guitar chords this weekend",
        "started learning guitar chords this weekend",
        "my sister visited from bangalore",
        "the dentist appointment went badly",
    )
    reply = "how's the guitar chords practice going? and did your sister enjoy bangalore? also that dentist appointment"
    used = moments_used(reply, "hi")
    assert len(used) == 2
    assert len({m["said"] for m in used}) == 2


def test_nothing_recalled_means_nothing_shown():
    recalled_moments.set(())
    assert moments_used("anything at all about guitar", "hi") == []
