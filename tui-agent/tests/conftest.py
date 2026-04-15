import pytest
from tui_agent.session import Session


@pytest.fixture
def echo_session():
    """Start a session running cat (echoes stdin to stdout)."""
    s = Session(name="test", cmd=["/bin/cat"], cols=80, rows=24)
    yield s
    s.close()


@pytest.fixture
def bash_session():
    """Start a session running bash with a known prompt."""
    s = Session(
        name="testbash",
        cmd=["/bin/bash", "--norc", "--noprofile"],
        cols=80,
        rows=24,
        env={"PS1": "READY$ "},
    )
    yield s
    s.close()
