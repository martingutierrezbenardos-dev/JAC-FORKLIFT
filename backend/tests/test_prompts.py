from datetime import date

from app.ai.prompts import SYSTEM_PROMPT, build_system_prompt


def test_build_system_prompt_incluye_la_fecha_de_hoy():
    hoy = date(2026, 9, 10)  # jueves

    prompt = build_system_prompt(today=hoy)

    assert "jueves 2026-09-10" in prompt
    assert prompt.startswith(SYSTEM_PROMPT)


def test_build_system_prompt_usa_date_today_por_defecto():
    prompt = build_system_prompt()

    assert date.today().isoformat() in prompt
