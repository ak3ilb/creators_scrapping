"""
chrome_fallback.py — Level 3: Fetch transcript via headless Chrome.

Opens the YouTube video page, clicks the transcript panel,
and scrapes timed captions when API methods fail.
"""

import time
import re
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import undetected_chromedriver as uc

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
        (segments, language, metadata) where segments is a list of {start, duration, text},
        language is the detected language code, and metadata is a dict with {title, description}.
    """
    driver = _create_driver()

    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        logger.info(f"[{video_id}] Chrome: loading {url}")
        try:
            driver.get(url)
        except TimeoutException:
            logger.info(f"[{video_id}] Page load timed out after 30s, proceeding anyway...")

        # Wait for page to load
        time.sleep(3)

        # 1. Extract Metadata (Title/Description)
        metadata = _extract_metadata(driver)

        # 2. Dismiss consent dialog if present
        _dismiss_consent(driver)

        # 3. Try to open transcript panel
        _open_transcript_panel(driver, timeout)

        # Wait for transcript segments to load
        time.sleep(2)

        # 4. Scrape transcript segments
        segments, language = _scrape_transcript(driver)

        if not segments:
            raise Exception("No transcript segments found in panel")

        logger.info(
            f"[{video_id}] Chrome: extracted {len(segments)} segments"
        )
        return segments, language, metadata

    finally:
        driver.quit()


def _create_driver():
    """Create an undetectable headless Chrome WebDriver."""
    options = uc.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    
    # Hide automation flags
    options.add_argument('--disable-blink-features=AutomationControlled')
    
    import sys
    if sys.platform == 'darwin':
        options.add_argument(
            '--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        )
    else:
        options.add_argument(
            '--user-agent=Mozilla/5.0 (X11; Linux x86_64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        )
    
    # Use undetected-chromedriver to bypass detection
    try:
        driver = uc.Chrome(options=options, version_main=131)
        logger.info("Undetectable Chrome driver created successfully.")
    except Exception as e:
        logger.warning(f"Undetectable driver failed: {e}. Falling back to standard...")
        # Emergency fallback (standard selenium)
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        std_options = Options()
        std_options.add_argument('--headless')
        std_options.add_argument('--no-sandbox')
        service = Service()
        driver = webdriver.Chrome(options=std_options, service=service)

    driver.implicitly_wait(5)
    driver.set_page_load_timeout(30)
    return driver


def _extract_metadata(driver):
    """Extract video title and description using Selenium."""
    meta = {"title": "Unknown", "description": ""}
    try:
        # Extract Title
        title_el = driver.find_elements(By.CSS_SELECTOR, 'h1.ytd-video-primary-info-renderer, #title h1, h1')
        if title_el:
            meta["title"] = title_el[0].text.strip()
        
        # Extract Description
        desc_el = driver.find_elements(By.CSS_SELECTOR, '#description-inline-expander, #description')
        if desc_el:
            meta["description"] = desc_el[0].text.strip()
    except Exception as e:
        logger.debug(f"Metadata extraction via Chrome failed: {e}")
    return meta


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
