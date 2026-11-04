import pytest
from PySide6.QtCore import QPoint

from cofre.services.vault_service import VaultService
from cofre.ui import main_view, theme
from cofre.ui.entry_dialog import EntryDialog
from cofre.ui.main_view import MainView, count_label
from cofre.ui.main_window import MainWindow
from cofre.ui.unlock_view import UnlockView
from cofre.ui.vault_mark import VaultMark

MASTER = "senha mestra de teste"
SCHEMES = [("claro", theme.LIGHT), ("escuro", theme.DARK)]


def luminance(color: str) -> float:
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(first: str, second: str) -> float:
    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize(("_name", "scheme"), SCHEMES)
def test_text_colors_meet_wcag_aa(_name, scheme):
    for text in (scheme.ink, scheme.muted, scheme.danger):
        for background in (scheme.background, scheme.surface):
            assert contrast(text, background) >= 4.5, (text, background)
    assert contrast(scheme.ink, scheme.selection) >= 4.5
    assert contrast(scheme.ink, scheme.hover) >= 4.5
    assert contrast(scheme.on_primary, scheme.primary) >= 4.5


@pytest.mark.parametrize(("_name", "scheme"), SCHEMES)
def test_interface_components_meet_wcag_non_text_contrast(_name, scheme):
    # Foco do teclado e borda dos campos precisam ser percebidos (3:1).
    for background in (scheme.background, scheme.surface):
        assert contrast(scheme.accent, background) >= 3
        assert contrast(scheme.field_border, background) >= 3


@pytest.mark.parametrize(("_name", "scheme"), SCHEMES)
def test_stylesheet_has_no_unresolved_placeholders(_name, scheme):
    css = theme.build_stylesheet(scheme)
    assert "$" not in css
    assert scheme.primary in css


def test_apply_scheme_switches_palette_and_current_colors(qapp):
    theme.apply_scheme(qapp, theme.DARK)
    assert theme.colors() is theme.DARK
    assert qapp.palette().window().color().name().upper() == theme.DARK.background
    theme.apply_scheme(qapp, theme.LIGHT)
    assert theme.colors() is theme.LIGHT
    assert qapp.palette().window().color().name().upper() == theme.LIGHT.background


def test_apply_uses_fusion_and_follows_the_system(qapp, monkeypatch):
    requested = []
    real_set_style = qapp.setStyle

    def recording_set_style(name):
        requested.append(name)
        real_set_style(name)

    monkeypatch.setattr(qapp, "setStyle", recording_set_style)
    theme.apply(qapp)
    assert requested == ["Fusion"]
    assert theme.colors() in (theme.LIGHT, theme.DARK)
    assert qapp.styleSheet() != ""


def test_mono_font_prefers_monospace_families():
    font = theme.mono_font(13)
    assert font.families()[0] == theme.MONO_FONTS[0]
    assert font.pointSizeF() == 13


@pytest.mark.parametrize(("_name", "scheme"), SCHEMES)
def test_vault_mark_paints_in_both_schemes(qtbot, qapp, _name, scheme):
    theme.apply_scheme(qapp, scheme)
    mark = VaultMark()
    qtbot.addWidget(mark)
    image = mark.grab().toImage()
    assert not image.isNull()
    assert image.width() == mark.width()
    assert len({image.pixel(x, y) for x in range(0, 76, 4) for y in range(0, 76, 4)}) > 3


@pytest.fixture
def service(tmp_path):
    created = VaultService(tmp_path / "v.cofre")
    created.create(MASTER, MASTER, acknowledged_no_recovery=True)
    return created


@pytest.mark.parametrize(
    ("total", "text"), [(0, "Nenhuma conta"), (1, "1 conta"), (2, "2 contas"), (12, "12 contas")]
)
def test_count_label(total, text):
    assert count_label(total) == text


def test_empty_state_invites_creating_the_first_account(qtbot, service):
    view = MainView(service)
    qtbot.addWidget(view)
    view.refresh()

    assert view.content.currentWidget() is view.empty_state
    assert view.count.text() == "Nenhuma conta"
    assert view.add_button.isHidden()
    assert all(
        button.isHidden()
        for button in (view.copy_button, view.reveal_button, view.edit_button, view.delete_button)
    )


def test_empty_state_button_opens_the_new_account_dialog(qtbot, service, monkeypatch):
    opened = []
    monkeypatch.setattr(
        main_view.EntryDialog, "exec", lambda dialog: opened.append(dialog.windowTitle()) or 0
    )
    view = MainView(service)
    qtbot.addWidget(view)
    view.refresh()
    view.empty_add_button.click()
    assert opened == ["Nova conta"]


def test_list_replaces_empty_state_when_there_are_accounts(qtbot, service):
    service.add_entry("GitHub", "ana", "senha-1")
    view = MainView(service)
    qtbot.addWidget(view)
    view.show()
    view.refresh()

    assert view.content.currentWidget() is view.table
    assert view.count.text() == "1 conta"
    assert view.add_button.isVisible()
    assert view.hint.isVisible()

    view.table.selectRow(0)
    assert not view.hint.isVisible()


def test_initial_focus_goes_to_the_list_or_to_the_first_account_button(qtbot, service):
    window = MainWindow(service)
    qtbot.addWidget(window)
    window.show()
    window._show_vault()
    qtbot.waitUntil(lambda: window.main_view.empty_add_button.hasFocus(), timeout=2000)

    service.add_entry("GitHub", "ana", "senha-1")
    window._show_vault()
    qtbot.waitUntil(lambda: window.main_view.table.hasFocus(), timeout=2000)
    window.idle_lock.stop()


def test_backup_lives_in_a_menu(qtbot, service):
    view = MainView(service)
    qtbot.addWidget(view)
    texts = [action.text() for action in view.backup_button.menu().actions()]
    assert texts == ["Exportar backup…", "Restaurar backup…"]


def test_backup_menu_actions_emit_requests(qtbot, service):
    view = MainView(service)
    qtbot.addWidget(view)
    with qtbot.waitSignal(view.export_requested, timeout=1000):
        view.export_action.trigger()
    with qtbot.waitSignal(view.restore_requested, timeout=1000):
        view.restore_action.trigger()


def test_context_menu_selects_the_row_and_offers_the_actions(qtbot, service, monkeypatch):
    service.add_entry("GitHub", "ana", "senha-1")
    service.add_entry("Banco", "ana", "senha-2")
    view = MainView(service)
    qtbot.addWidget(view)
    view.resize(600, 400)
    view.show()
    view.refresh()
    seen = []
    monkeypatch.setattr(
        MainView,
        "_exec_menu",
        lambda _self, menu, _pos: seen.append([a.text() for a in menu.actions() if a.text()]),
    )

    row_center = view.table.visualItemRect(view.table.item(1, 0)).center()
    view._show_context_menu(row_center)

    assert view.table.currentRow() == 1
    assert seen == [["Copiar senha", "Revelar", "Editar", "Excluir"]]


def test_context_menu_ignores_empty_area(qtbot, service, monkeypatch):
    service.add_entry("GitHub", "ana", "senha-1")
    view = MainView(service)
    qtbot.addWidget(view)
    view.resize(600, 400)
    view.show()
    view.refresh()
    monkeypatch.setattr(MainView, "_exec_menu", lambda *_a: pytest.fail("menu não deveria abrir"))
    view._show_context_menu(QPoint(5, view.table.viewport().height() - 5))


def test_errors_are_styled_and_clear_afterwards(qtbot, service, monkeypatch):
    import os

    service.add_entry("GitHub", "ana", "senha-1")
    view = MainView(service)
    qtbot.addWidget(view)
    view.refresh()
    view._confirm_delete = lambda *_args: True
    monkeypatch.setattr(os, "replace", lambda *_a: (_ for _ in ()).throw(OSError("x")))
    view.table.selectRow(0)
    view.delete_button.click()
    assert view.status.property("kind") == "error"

    view.show_status("Tudo certo.")
    assert view.status.property("kind") == ""


def test_unlock_error_is_styled_and_notice_is_not(qtbot, tmp_path):
    created = VaultService(tmp_path / "novo.cofre")
    created.create(MASTER, MASTER, acknowledged_no_recovery=True)
    created.lock()
    view = UnlockView(created)
    qtbot.addWidget(view)

    view.password.setText("senha errada qualquer")
    with qtbot.waitSignal(view._runner.failed, timeout=10000):
        view.submit.click()
    assert view.message.property("kind") == "error"

    view.reset("Cofre bloqueado por inatividade.")
    assert view.message.property("kind") == ""


def test_master_password_can_be_shown_and_resets_to_hidden(qtbot, service):
    service.lock()
    view = UnlockView(service)
    qtbot.addWidget(view)
    view.show_button.click()
    assert view.password.echoMode() == view.password.EchoMode.Normal
    assert view.confirmation.echoMode() == view.confirmation.EchoMode.Normal
    assert view.show_button.text() == "Ocultar"

    view.reset()
    assert view.password.echoMode() == view.password.EchoMode.Password
    assert view.show_button.text() == "Mostrar"


def test_unlock_screen_explains_each_mode(qtbot, tmp_path):
    fresh = UnlockView(VaultService(tmp_path / "x.cofre"))
    qtbot.addWidget(fresh)
    assert fresh.title.text() == "Criar cofre"
    assert "12 ou mais caracteres" in fresh.hint.text()

    existing = VaultService(tmp_path / "y.cofre")
    existing.create(MASTER, MASTER, acknowledged_no_recovery=True)
    opened = UnlockView(existing)
    qtbot.addWidget(opened)
    assert opened.title.text() == "Abrir cofre"
    assert "12 ou mais" not in opened.hint.text()


def test_generator_options_start_collapsed_and_toggle(qtbot, service):
    dialog = EntryDialog(service)
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.options_box.isHidden()
    dialog.options_button.click()
    assert dialog.options_box.isVisible()
    dialog.options_button.click()
    assert dialog.options_box.isHidden()


def test_dialog_error_message_is_styled(qtbot, service):
    dialog = EntryDialog(service)
    qtbot.addWidget(dialog)
    dialog.save_button.click()
    assert dialog.message.property("kind") == "error"
    dialog.generate_button.click()
    assert dialog.message.property("kind") == ""
