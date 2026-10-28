from alfiebot.core.state_machine import StateMachine
from alfiebot.core.states import STATE_EXPRESSIONS, Expression, RobotState
from alfiebot.face.poses import BEHAVIOURS, POSES


def test_all_ten_states_and_eighteen_expressions_exist():
    assert len(RobotState) == 10
    assert [e.value for e in Expression] == [
        "neutral", "happy", "curious", "sleepy", "surprised", "looking_left", "looking_right",
        "looking_around", "thinking", "confused", "sad", "angry", "love", "wink", "processing",
        "sleeping", "listening", "excited"]


def test_every_state_has_an_expression():
    assert set(STATE_EXPRESSIONS) == set(RobotState)


def test_every_expression_has_a_pose_and_behaviour():
    assert set(POSES) == set(Expression)
    assert set(BEHAVIOURS) == set(Expression)


def test_state_machine_notifies_listeners():
    sm = StateMachine(RobotState.SLEEPING)
    seen = []
    sm.add_listener(lambda old, new: seen.append((old, new)))
    assert sm.set_state(RobotState.IDLE)
    assert not sm.set_state(RobotState.IDLE)
    assert seen == [(RobotState.SLEEPING, RobotState.IDLE)]


def test_time_in_state_resets_on_change():
    sm = StateMachine()
    sm.update(2.0)
    assert sm.time_in_state == 2.0
    sm.set_state(RobotState.LISTENING)
    assert sm.time_in_state == 0.0
