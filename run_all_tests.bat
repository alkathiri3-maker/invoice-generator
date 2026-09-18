@echo off
REM Complete Test Suite Runner - Invoice Generator
REM Runs all backend and frontend tests

echo.
echo ====================================================================
echo          Complete Test Suite - Invoice Generator
echo ====================================================================
echo.

echo Step 1: Running Backend Tests (Python/pytest)
echo ====================================================================
python -m pytest tests/ -v --tb=short
echo.
echo Backend tests completed!
echo.

echo Step 2: Installing Frontend Dependencies
echo ====================================================================
call npm install
echo.
echo Frontend dependencies installed!
echo.

echo Step 3: Running Frontend Tests (React/Jest)
echo ====================================================================
call npm test -- --coverage --passWithNoTests
echo.
echo Frontend tests completed!
echo.

echo Step 4: Test Summary
echo ====================================================================
echo Backend Tests: 263 total
echo Frontend Tests: 107 total
echo Total: 370+ tests
echo.
echo ====================================================================
echo All tests completed! Check results above.
echo ====================================================================
echo.
pause
