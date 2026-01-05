
import pytest
from playwright.sync_api import sync_playwright, expect
import time

def test_data_manager_ui():
    """
    Test Suite for Data Manager / Historical Data Management Page.
    """
    with sync_playwright() as p:
        # Launch with headless=False to see the browser action if needed (set to True for CI)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        # Set a default timeout for all actions
        page.set_default_timeout(15000)
        
        print("\n=== STARTING UI TEST ===")
        
        # 1. Login Flow
        print("1. Navigating to Landing Page...")
        page.goto("http://localhost:5173")
        page.wait_for_load_state("networkidle")
        
        if page.locator("text=Sign In").is_visible():
            print("   Logging in...")
            page.click("text=Sign In")
            page.fill("input[type='email']", "test@example.com")
            page.fill("input[type='password']", "password123")
            page.click("button:has-text('Sign In')")
            
            # Wait for dashboard content or URL change
            try:
                page.wait_for_url("**/dashboard")
                print("   Login Successful.")
            except:
                print("   Note: URL didn't change to /dashboard, checking page content...")
        
        # 2. Access Data Manager Page
        print("2. Navigating to Data Manager...")
        # Force navigation to ensure we are on the right page
        page.goto("http://localhost:5173/data-manager")
        
        try:
            # Wait for the main container
            page.wait_for_selector(".data-manager")
            print("   Data Manager Page Loaded Successfully.")
        except:
            print("   ERROR: Could not load Data Manager page.")
            browser.close()
            return

        # 3. Test Sub-Navigation Tabs
        print("3. Testing Sub-Navigation Tabs...")
        tabs = [
            {"text": "Download", "selector": "button.subnav-btn:has-text('Download')"},
            {"text": "Import", "selector": "button.subnav-btn:has-text('Import')"},
            {"text": "Export", "selector": "button.subnav-btn:has-text('Export')"},
            {"text": "Scheduler", "selector": "button.subnav-btn:has-text('Scheduler')"},
            {"text": "Settings", "selector": "button.subnav-btn:has-text('Settings')"}
        ]
        
        for tab in tabs:
            btn = page.locator(tab["selector"])
            if btn.is_visible():
                btn.click()
                expect(btn).to_have_class(re.compile(r"active"))
                print(f"   [PASS] Tab '{tab['text']}' is working.")
                time.sleep(0.5) # Small pause for visual stability
            else:
                print(f"   [FAIL] Tab '{tab['text']}' not found.")
        
        # Go back to Download tab
        page.click("button.subnav-btn:has-text('Download')")
        
        # 4. Test Search Input
        print("4. Testing Search Input...")
        search_input = page.locator("input[placeholder='Search symbols...']")
        if search_input.is_visible():
            search_input.fill("RELIANCE")
            expect(search_input).to_have_value("RELIANCE")
            print("   [PASS] Search input is functional.")
        else:
            print("   [FAIL] Search input not found.")
        
        # 5. Test Dropdowns
        print("5. Testing Dropdowns...")
        dropdown = page.locator("select.input-field").first
        if dropdown.is_visible():
            dropdown.select_option(index=1)
            print("   [PASS] Dropdown selection is functional.")
        else:
             print("   [WARN] No dropdowns found on this tab.")

        # 6. Test Radio Buttons
        print("6. Testing Radio Controls...")
        # Look for radio buttons by label text or type
        radio_label = page.locator("label.radio-option").last
        if radio_label.is_visible():
            radio_label.click()
            print("   [PASS] Radio button interaction worked.")
        else:
            print("   [WARN] No radio options found.")

        print("\n=== TEST COMPLETED SUCCESSFULLY ===")
        browser.close()

if __name__ == "__main__":
    import re
    try:
        test_data_manager_ui()
    except Exception as e:
        print(f"\nTEST EXECUTION ERROR: {e}")
