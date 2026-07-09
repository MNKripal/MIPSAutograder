import subprocess
import json
import re

def run_test(val_a0, val_a1):
    # 1. Create the test harness
    harness = f"""
    .data
    array: .word 0:10  # Reserve space for A[0] through A[9]
    .text
    main:
        la $s0, array
        li $t0, {val_a0}
        sw $t0, 0($s0)   # Set A[0]
        li $t1, {val_a1}
        sw $t1, 4($s0)   # Set A[1]
        jal student_code
        li $v0, 10       # Exit
        syscall
    """
    
    # 2. Combine harness with student submission
    with open('submission.s', 'r') as f:
        student_code = f.read()
    
    with open('test_run.s', 'w') as f:
        f.write(harness + "\n" + "student_code:\n" + student_code)

    # 3. Run SPIM and capture memory
    result = subprocess.run(['spim', '-file', 'test_run.s'], capture_output=True, text=True)
    return result.stdout

# Logic to parse memory and generate Gradescope's results.json goes here
