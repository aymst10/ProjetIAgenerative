"""Le RNN du cours apprend la sinusoïde sur CPU, sans poids externes."""

import torch

from notebooks.sequence_models import MiniTransformer, SimpleLSTM, SimpleRNN, make_windows, train_and_eval


def test_windows_follow_the_course_split():
    _periode, _serie, x_train, y_train, x_test, y_test = make_windows()
    assert tuple(x_train.shape) == (150, 10, 1)
    assert tuple(y_train.shape) == (150, 1)
    assert tuple(x_test.shape) == (40, 10, 1)
    assert tuple(y_test.shape) == (40, 1)


def test_rnn_loss_drops_on_cpu():
    torch.manual_seed(42)
    _periode, _serie, x_train, y_train, x_test, y_test = make_windows()
    resultat = train_and_eval(
        SimpleRNN(),
        x_train,
        y_train,
        x_test,
        y_test,
        epochs=60,
        log=False,
    )
    assert resultat["predictions"].shape == y_test.shape
    assert resultat["history"][-1] < resultat["history"][0]
    assert resultat["test_loss"] < 0.2


def test_lstm_loss_drops_on_cpu():
    torch.manual_seed(42)
    _periode, _serie, x_train, y_train, x_test, y_test = make_windows()
    resultat = train_and_eval(
        SimpleLSTM(),
        x_train,
        y_train,
        x_test,
        y_test,
        epochs=60,
        log=False,
    )
    assert resultat["predictions"].shape == y_test.shape
    assert resultat["history"][-1] < resultat["history"][0]
    assert resultat["test_loss"] < 0.2


def test_transformer_loss_drops_on_cpu():
    torch.manual_seed(42)
    _periode, _serie, x_train, y_train, x_test, y_test = make_windows()
    resultat = train_and_eval(
        MiniTransformer(longueur_max=10),
        x_train,
        y_train,
        x_test,
        y_test,
        epochs=80,
        log=False,
    )
    assert resultat["predictions"].shape == y_test.shape
    assert resultat["history"][-1] < resultat["history"][0]
    assert resultat["test_loss"] < 0.2
