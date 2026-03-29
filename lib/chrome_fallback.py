"""
chrome_fallback.py — Level 3: Fetch transcript via headless Chrome.

Opens the YouTube video page, clicks the transcript panel,
and scrapes timed captions when API methods fail.
"""

import time
import re
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)

# Suppress noisy Selenium logs
logging.getLogger("selenium").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


def fetch_transcript_via_chrome(
    video_id: str,
    languages: list[str] = None,
    timeout: int = 20,
) -> tuple[list[dict], str]:
    """
    Open a YouTube Shorts video in headless Chrome, open the transcript
    panel, and scrape the timed captions.

    Args:
        video_id: YouTube video ID
        languages: preferred language codes (used for reporting only)
        timeout: max seconds to wait for elements

    Returns:
        (segments, language) where segments is a list of {start, duration, text}
        and language is the detected language code.

    Raises:
        Exception if transcript cannot be extracted.
    """
    driver = _create_driver()

    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        logger.info(f"[{video_id}] Chrome: loading {url}")
        driver.get(url)

        # Wait for page to load
        time.sleep(3)

        # Dismiss consent dialog if present
        _dismiss_consent(driver)

        # Try to open transcript panel
        _open_transcript_panel(driver, timeout)

        # Wait for transcript segments to load
        time.sleep(2)

        # Scrape transcript segments
        segments, language = _scrape_transcript(driver)

        if not segments:
            raise Exception("No transcript segments found in panel")

        logger.info(
            f"[{video_id}] Chrome: extracted {len(segments)} segments"
        )
        return segments, language

    finally:
        driver.quit()


def _create_driver():
    """Create a headless Chrome WebDriver."""
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument(
        '--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    )

    # In Selenium 4.10+, Selenium Manager is built-in and handles driver downloads.
    # However, if an old 'chromedriver' exists in the system PATH (e.g., version 133), 
    # Selenium might try to use it and fail against Chrome 146.
    
    # We attempt to clear the path of common 'bad' locations temporarily 
    # to force Selenium Manager to do its job properly.
    import os
    old_path = os.environ.get('PATH', '')
    # Remove common homebrew/local paths where an old chromedriver might hide
    bad_dirs = ['/opt/homebrew/bin', '/usr/local/bin', '/usr/bin', '/bin']
    new_path = ":".join([p for p in old_path.split(':') if p not in bad_dirs])
    
    try:
        # First attempt: Try with the modified PATH to let Selenium Manager download the correct driver
        os.environ['PATH'] = new_path
        service = Service()
        driver = webdriver.Chrome(options=options, service=service)
        logger.info("Chrome driver created successfully via Selenium Manager.")
    except Exception as e:
        logger.warning(f"Initial driver creation failed: {e}. Retrying with original PATH...")
        os.environ['PATH'] = old_path
        try:
            service = Service()
            driver = webdriver.Chrome(options=options, service=service)
        except Exception as e2:
            logger.error(f"Final driver creation failure: {e2}")
            raise e2
    finally:
        # Restore PATH so other tools (like yt-dlp) still work
        os.environ['PATH'] = old_path
            
    driver.implicitly_wait(5)
    return driver


def _dismiss_consent(driver):
    """Click through any YouTube consent/cookie dialogs."""
    try:
        # Look for consent button
        buttons = driver.find_elements(
            By.CSS_SELECTOR,
            'button[aria-label*="Accept"], button[aria-label*="Reject"], '
            'button.yt-spec-button-shape-next'
        )
        for btn in buttons:
            text = btn.text.lower()
            if 'accept' in text or 'agree' in text:
                btn.click()
                time.sleep(1)
                break
    except Exception:
        pass


def _open_transcript_panel(driver, timeout: int):
    """
    Click the '...more' or description area, then find and click
    'Show transcript' button.
    """
    # Strategy 1: Click the three-dot menu on the video
    try:
        # Look for the "more actions" or description expand
        more_btn = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                '#expand, tp-yt-paper-button#expand, '
                '#description-inline-expander ytd-text-inline-expander-renderer #expand'
            ))
        )
        more_btn.click()
        time.sleep(1)
    except Exception:
        logger.debug("Could not click expand button")

    # Look for "Show transcript" button/link
    try:
        transcript_btn = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((
                By.XPATH,
                '//*[contains(text(), "Show transcript") or '
                'contains(text(), "Transcript") or '
                'contains(@aria-label, "transcript") or '
                '//button[contains(@aria-label, "Transcript")] or '
                '//ytd-button-renderer[contains(., "Transcript")]'
                ']'
            ))
        )
        transcript_btn.click()
        time.sleep(2)
        return
    except Exception:
        pass

    # Strategy 2: Look for the 'Show transcript' button specifically in ytd-video-description-transcript-section-renderer
    try:
        section_btn = driver.find_element(
            By.CSS_SELECTOR,
            'ytd-video-description-transcript-section-renderer button'
        )
        section_btn.click()
        time.sleep(2)
        return
    except Exception:
        pass

    # Strategy 2: Try the three-dot menu → "Open transcript"
    try:
        menu_btn = driver.find_element(
            By.CSS_SELECTOR,
            'button.ytp-button[data-tooltip-target-id="ytp-autonav-toggle-button"], '
            '#menu-button button, '
            'ytd-menu-renderer button'
        )
        menu_btn.click()
        time.sleep(1)

        transcript_option = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((
                By.XPATH,
                '//tp-yt-paper-listbox//yt-formatted-string[contains(text(), '
                '"transcript") or contains(text(), "Transcript")]'
            ))
        )
        transcript_option.click()
        time.sleep(2)
    except Exception:
        raise Exception("Could not open transcript panel")


def _scrape_transcript(driver) -> tuple[list[dict], str]:
    """
    Scrape transcript segments from the open transcript panel.

    Returns (segments, language_code).
    """
    segments = []
    language = 'unknown'

    try:
        # Find transcript segment elements
        # YouTube transcript panel structure (Shorts / Modern desktop):
        # transcript-segment-view-model contains timestamp + text
        seg_elements = driver.find_elements(By.CSS_SELECTOR, 'transcript-segment-view-model')

        if not seg_elements:
            # Fallback 1: Generic/Legacy structure
            seg_elements = driver.find_elements(
                By.CSS_SELECTOR,
                'ytd-transcript-segment-renderer, '
                'ytd-transcript-segment-list-renderer '
                'ytd-transcript-segment-renderer'
            )

        if not seg_elements:
            # Fallback 2: try generic segment containers
            seg_elements = driver.find_elements(
                By.CSS_SELECTOR,
                '[class*="segment"]'
            )

        for seg_el in seg_elements:
            try:
                # Extract timestamp
                # Modern selector: .ytwTranscriptSegmentViewModelTimestamp
                try:
                    ts_el = seg_el.find_element(
                        By.CSS_SELECTOR,
                        '.ytwTranscriptSegmentViewModelTimestamp, .segment-timestamp, [class*="timestamp"]'
                    )
                    timestamp_text = ts_el.text.strip()
                except Exception:
                    timestamp_text = None

                # Extract text
                # Modern selector: span.yt-core-attributed-string
                try:
                    text_el = seg_el.find_element(
                        By.CSS_SELECTOR,
                        'span.yt-core-attributed-string, .segment-text, [class*="segment-text"], yt-formatted-string.segment-text'
                    )
                    segment_text = text_el.text.strip()
                except Exception:
                    segment_text = None

                if timestamp_text and segment_text:
                    start_seconds = _parse_timestamp(timestamp_text)
                    segments.append({
                        'start': start_seconds,
                        'duration': 0.0,  # Chrome can't give us duration easily
                        'text': segment_text,
                    })
            except Exception:
                continue

        # Try to detect language from transcript panel header
        try:
            lang_el = driver.find_element(
                By.CSS_SELECTOR,
                '#footer yt-formatted-string, '
                'ytd-transcript-footer-renderer yt-formatted-string'
            )
            lang_text = lang_el.text.lower()
            if 'hindi' in lang_text:
                language = 'hi'
            elif 'english' in lang_text:
                language = 'en'
        except Exception:
            pass

    except Exception as e:
        logger.warning(f"Chrome scrape error: {e}")

    # Compute durations from start times
    for i in range(len(segments) - 1):
        segments[i]['duration'] = segments[i + 1]['start'] - segments[i]['start']
    if segments:
        segments[-1]['duration'] = 3.0  # estimate for last segment

    return segments, language


def _parse_timestamp(ts: str) -> float:
    """
    Parse a timestamp like '0:42' or '1:05' into seconds.
    """
    ts = ts.strip()
    parts = ts.split(':')
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        else:
            return float(ts)
    except ValueError:
        return 0.0
