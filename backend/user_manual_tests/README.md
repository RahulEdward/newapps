
# User Manual Tests

This directory contains automated test scripts for verifying the functionality of the Data Manager and other application components.

## Prerequisites

Ensure you have the required Python packages installed:

```bash
pip install playwright pytest
playwright install chromium
```

## Running the Tests

To run the Data Manager UI test, execute the following command from the `backend` directory:

```bash
python user_manual_tests/test_data_manager_ui.py
```

## Test Coverage

The `test_data_manager_ui.py` script verifies:
1.  **Authentication**: Logs in to the application.
2.  **Navigation**: Accesses the Data Manager page.
3.  **Tabs**: Clicks through valid tabs (Download, Import, Export, Scheduler, Settings).
4.  **Inputs**: Tests text inputs (Search), Dropdowns (Interval), and Radio buttons (fresh vs continue).
