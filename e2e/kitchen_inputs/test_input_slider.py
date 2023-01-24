from conftest import ShinyAppProc, create_doc_example_fixture
from playground import InputSlider, OutputTextVerbatim
from playwright.sync_api import Page, expect

slider_app = create_doc_example_fixture("input_slider")
template_app = create_doc_example_fixture("template")


def test_input_slider_kitchen(page: Page, slider_app: ShinyAppProc) -> None:
    page.goto(slider_app.url)

    # page.set_default_timeout(1000)

    obs = InputSlider(page, "obs")
    # file1.expect.to_have_value("Data summary")
    # expect(file1.loc).to_have_value("Data summary")

    expect(obs.loc_label).to_have_text("Number of bins:")

    obs.expect_animate(False)
    # obs.expect_animate_interval_to_have_value(500)
    # obs.expect_animate_loop_to_have_value(True)
    obs.expect_min_to_have_value("10")
    obs.expect_max_to_have_value("100")
    # obs.expect_from_to_have_value()
    obs.expect_step_to_have_value("1")
    obs.expect_ticks_to_have_value("true")
    obs.expect_sep_to_have_value(",")
    obs.expect_pre_to_have_value(None)
    obs.expect_post_to_have_value(None)
    # obs.expect_data_type_to_have_value()
    obs.expect_time_format_to_have_value(None)
    obs.expect_timezone_to_have_value(None)
    obs.expect_drag_range_to_have_value(None)

    obs.set(42.0 / 100.0)

    # TODO-barret; test plot output


def test_input_slider_output(page: Page, template_app: ShinyAppProc) -> None:
    page.goto(template_app.url)

    slider = InputSlider(page, "n")
    txt = OutputTextVerbatim(page, "txt")

    txt.expect_value("n*2 is 40")
    slider.expect_label_to_have_text("N")
    # slider.expect_value("20")

    slider.set(42.0 / 100.0)
    # slider.expect_value("42")

    txt.expect_value("n*2 is 84")