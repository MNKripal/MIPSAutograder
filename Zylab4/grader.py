#!/usr/bin/env python3
"""
Gradescope Autograder for MIPS Assignment (Question 4)
Uses the instructor's MIPS code as the oracle solution.
"""

import json
import os
import subprocess
import re

# ----------------------------------------------------------------------
# Professor's MIPS solution
# ----------------------------------------------------------------------
PROF_SOLUTION = """\
Main:
    addi $a0,$s0,0
    addi $a1,$s2,0
    addi $a2,$s1,0
    jal Insert

Ret:
    addi $s3,$v0,0
    j Exit

Insert:
    bne $a1,$zero,C_find

    sw $a0,4($a2)
    addi $s0,$a2,0
    j R_insert

C_find:
    addi $sp,$sp,-4
    sw $ra,0($sp)

    jal Find

    sw $a2,4($v0)
    sw $v1,4($a2)

    lw $ra,0($sp)
    addi $sp,$sp,4

R_insert:
    lw $v0,0($a2)
    jr $ra

Find:
    addi $v0,$a0,0
    addi $t0,$zero,1

Loop:
    bge $t0,$a1,R_find

    lw $v0,4($v0)
    lw $t1,4($v0)

    beq $t1,$zero,R_find

    addi $t0,$t0,1
    j Loop

R_find:
    lw $v1,4($v0)
    jr $ra

Exit:
"""

# ----------------------------------------------------------------------
# Hidden Test Cases
# ----------------------------------------------------------------------
TEST_CASES = [
    {
        "name": "Test Case 1",
        "s0": 4000,
        "s1": 8000,
        "s2": 2,
        "s3": 0,
        "memory": {
            3848: -15,
            3852: 6104,
            4000: 4,
            4004: 3848,
            4500: 40,
            4504: 0,
            5008: 0,
            5012: 4500,
            6104: -10,
            6108: 5008,
            8000: 230
        }
    },
    {
        "name": "Test Case 2",
        "s0": 13804,
        "s1": 4000,
        "s2": 0,
        "s3": 0,
        "memory": {
            4000: -230,
            8000: 80,
            8004: 0,
            13804: -8,
            13808: 8000
        }
    },
    {
        "name": "Test Case 3",
        "s0": 8016,
        "s1": 13000,
        "s2": 100,
        "s3": 0,
        "memory": {
            4024: 100,
            4028: 6032,
            6032: -80,
            6036: 0,
            8016: -50,
            8020: 8040,
            8040: -100,
            8044: 4024,
            13000: 0
        }
    },
    {
        "name": "Test Case 4",
        "s0": 10000,
        "s1": 4024,
        "s2": 3,
        "s3": 0,
        "memory": {
            4024: 30,
            5008: -5,
            5012: 8016,
            8016: 20,
            8020: 0,
            10000: 23,
            10004: 5008
        }
    }
]


def find_student_submission(submission_dir="/autograder/submission"):
    """
    Recursively searches the submission directory for a valid MIPS file
    (.asm or .asm.txt), ignoring macOS metadata files starting with '._'.
    """
    if not os.path.exists(submission_dir):
        # Fallback to local directory for debugging/local testing
        submission_dir = "./submission"
        if not os.path.exists(submission_dir):
            return None

    for root, dirs, files in os.walk(submission_dir):
        for f in files:
            # Skip macOS metadata files
            if f.startswith("._"):
                continue
            if f.endswith(".asm") or f.endswith(".asm.txt"):
                return os.path.join(root, f)
    return None


def build_harness(mips_code, s0_val, s1_val, s2_val, s3_val, memory_init):
    """
    Generates a complete MIPS test harness assembly program.
    Initializes register inputs and linked-list memory layouts dynamically by relative offset mapping,
    executes the student/instructor MIPS code, and then prints the final registers and memory values.
    """
    # Create a local copy of memory_init to add the newNode next pointer (offset 4) if not present
    mem_init = dict(memory_init)
    if s1_val != 0 and (s1_val + 4) not in mem_init:
        mem_init[s1_val + 4] = 0

    # Collect all addresses to map to safe SPIM memory
    all_addresses = list(mem_init.keys()) + [s0_val, s1_val]
    all_addresses = [addr for addr in all_addresses if addr != 0]
    min_val = min(all_addresses)

    def get_offset(addr):
        return addr - min_val + 1000

    # Generate memory initialization instructions
    init_instrs = []
    init_instrs.append("    la $t9, __Memory")

    for addr, val in mem_init.items():
        offset_addr = get_offset(addr)
        # Check if the address contains a pointer
        # (address - 4) being in the keys implies this address is a next pointer field
        is_ptr = (addr - 4) in mem_init

        if is_ptr and val != 0:
            # Load the mapped address of the pointer value into a register and store it
            offset_val = get_offset(val)
            init_instrs.append(f"    la $t0, {offset_val}($t9)")
            init_instrs.append(f"    sw $t0, {offset_addr}($t9)")
        else:
            init_instrs.append(f"    li $t0, {val}")
            init_instrs.append(f"    sw $t0, {offset_addr}($t9)")

    memory_initialization_code = "\n".join(init_instrs)

    # Setup register inputs
    reg_setup = []
    if s0_val == 0:
        reg_setup.append("    li $s0, 0")
    else:
        reg_setup.append(f"    la $s0, {get_offset(s0_val)}($t9)")

    if s1_val == 0:
        reg_setup.append("    li $s1, 0")
    else:
        reg_setup.append(f"    la $s1, {get_offset(s1_val)}($t9)")

    reg_setup.append(f"    li $s2, {s2_val}")
    reg_setup.append(f"    li $s3, {s3_val}")
    register_setup_code = "\n".join(reg_setup)

    # Print memory values in sorted order
    sorted_addresses = sorted(list(mem_init.keys()))
    print_mem_instrs = []
    for addr in sorted_addresses:
        offset_addr = get_offset(addr)
        print_mem_instrs.append(f"""\
    # Print address {addr}
    li $v0, 1
    li $a0, {addr}
    syscall
    li $v0, 4
    la $a0, __space_msg
    syscall
    # Load value and print translated
    la $t0, __Memory
    lw $a0, {offset_addr}($t0)
    jal __translate_and_print""")

    print_memory_code = "\n".join(print_mem_instrs)

    harness = f"""\
.data
.align 2
__Memory:
.space 20000

__s0_prefix: .asciiz "s0: "
__s1_prefix: .asciiz "s1: "
__s2_prefix: .asciiz "s2: "
__s3_prefix: .asciiz "s3: "
__space_msg: .asciiz " "
__newline_msg: .asciiz "\\n"

.text
.globl main
main:
    # Initialize memory
{memory_initialization_code}

    # Setup registers
{register_setup_code}

    # Execute student/instructor code
{mips_code}

    # Save final results before syscalls (which modify $a0, $v0)
    move $s6, $s0  # final $s0
    move $s7, $s1  # final $s1
    move $t4, $s2  # final $s2
    move $t5, $s3  # final $s3

    # Print s0
    li $v0, 4
    la $a0, __s0_prefix
    syscall
    move $a0, $s6
    jal __translate_and_print

    # Print s1
    li $v0, 4
    la $a0, __s1_prefix
    syscall
    move $a0, $s7
    jal __translate_and_print

    # Print s2
    li $v0, 4
    la $a0, __s2_prefix
    syscall
    move $a0, $t4
    jal __translate_and_print

    # Print s3
    li $v0, 4
    la $a0, __s3_prefix
    syscall
    move $a0, $t5
    jal __translate_and_print

    # Print memory values
{print_memory_code}

    # Clean exit
    li $v0, 10
    syscall

__translate_and_print:
    la $t0, __Memory
    addi $t0, $t0, 1000
    la $t8, __Memory
    addi $t8, $t8, 20000
    blt $a0, $t0, __print_val
    bgt $a0, $t8, __print_val
    # Translate pointer back to nominal
    sub $a0, $a0, $t0
    addi $a0, $a0, {min_val}
__print_val:
    li $v0, 1
    syscall
    li $v0, 4
    la $a0, __newline_msg
    syscall
    jr $ra
"""
    return harness


def run_spim(asm_path, timeout_seconds=5):
    """
    Executes the specified assembly file in SPIM and returns stdout combined with stderr.
    Throws TimeoutError or RuntimeError on failure.
    """
    try:
        run = subprocess.run(
            ["spim", "-file", asm_path],
            capture_output=True,
            text=True,
            timeout=timeout_seconds
        )
        return run.stdout + run.stderr
    except subprocess.TimeoutExpired as e:
        raise TimeoutError(f"SPIM execution timed out after {timeout_seconds} seconds.") from e
    except Exception as e:
        raise RuntimeError(f"Failed to execute SPIM: {str(e)}") from e


def check_spim_errors(spim_output):
    """
    Checks SPIM output for compiler or execution errors.
    Returns a string containing the error lines if found, or None if clean.
    """
    error_lines = []
    for line in spim_output.splitlines():
        # Skip standard exception file loading logs
        if "exceptions.s" in line or "Loaded:" in line:
            continue
        
        lower_line = line.lower()
        if (
            "error" in lower_line or 
            "exception" in lower_line or 
            "attempt to" in lower_line or 
            "undefined symbol" in lower_line or
            "spim:" in lower_line
        ):
            error_lines.append(line.strip())
            
    if error_lines:
        return "\n".join(error_lines)
    return None


def parse_registers(spim_output):
    """
    Parses the SPIM output to extract s0, s1, s2, s3 final values.
    """
    registers = {}
    for line in spim_output.splitlines():
        match = re.match(r"^(s0|s1|s2|s3):\s*(-?\d+)", line.strip())
        if match:
            registers[match.group(1)] = int(match.group(2))
    for reg in ["s0", "s1", "s2", "s3"]:
        if reg not in registers:
            raise ValueError(f"Could not find register {reg} in SPIM output.")
    return registers


def parse_memory(spim_output):
    """
    Parses SPIM output memory printout to produce a dictionary: address -> value.
    """
    memory = {}
    for line in spim_output.splitlines():
        match = re.match(r"^(\d+)\s+(-?\d+)$", line.strip())
        if match:
            addr = int(match.group(1))
            val = int(match.group(2))
            memory[addr] = val
    return memory


def grade_testcase(test_case, student_code):
    """
    Runs a single test case. Builds and executes harnesses for both the
    professor's solution and the student's solution, then compares the output.
    """
    s0 = test_case["s0"]
    s1 = test_case["s1"]
    s2 = test_case["s2"]
    s3 = test_case["s3"]
    memory = test_case["memory"]
    name = test_case["name"]

    # 1. Instructor Oracle Execution
    prof_harness = build_harness(PROF_SOLUTION, s0, s1, s2, s3, memory)
    prof_asm_path = f"/tmp/prof_harness_{s0}_{s2}.asm"
    prof_output = ""
    try:
        with open(prof_asm_path, "w") as f:
            f.write(prof_harness)
        prof_output = run_spim(prof_asm_path)
        
        prof_error = check_spim_errors(prof_output)
        if prof_error:
            raise RuntimeError(f"Oracle solution run produced error:\n{prof_error}")
            
        prof_regs = parse_registers(prof_output)
        prof_mem = parse_memory(prof_output)
    except Exception as e:
        cleaned_output = prof_output.strip() if prof_output else ""
        student_res = {
            "name": name,
            "score": 0.0,
            "max_score": 1.0,
            "status": "failed",
            "output": "Fail"
        }
        instructor_detail = f"Internal Error executing instructor solution: {str(e)}\n\nSPIM Output:\n{cleaned_output}"
        return student_res, instructor_detail
    finally:
        if os.path.exists(prof_asm_path):
            try:
                os.remove(prof_asm_path)
            except:
                pass

    # 2. Student Submission Execution
    student_harness = build_harness(student_code, s0, s1, s2, s3, memory)
    student_asm_path = f"/tmp/student_harness_{s0}_{s2}.asm"
    student_output = ""
    try:
        with open(student_asm_path, "w") as f:
            f.write(student_harness)
        student_output = run_spim(student_asm_path)
        
        student_error = check_spim_errors(student_output)
        if student_error:
            raise RuntimeError(f"SPIM error during execution:\n{student_error}")
            
        student_regs = parse_registers(student_output)
        student_mem = parse_memory(student_output)
    except Exception as e:
        cleaned_output = student_output.strip() if student_output else ""
        student_res = {
            "name": name,
            "score": 0.0,
            "max_score": 1.0,
            "status": "failed",
            "output": "Fail"
        }
        instructor_detail = f"Execution/Parsing failed.\nError: {str(e)}\n\nSPIM Output:\n{cleaned_output}"
        return student_res, instructor_detail
    finally:
        if os.path.exists(student_asm_path):
            try:
                os.remove(student_asm_path)
            except:
                pass

    # 3. Compare Results
    reg_mismatches = []
    for reg in ["s0", "s1", "s2", "s3"]:
        if student_regs[reg] != prof_regs[reg]:
            reg_mismatches.append(f"${reg} mismatch: Expected {prof_regs[reg]}, Got {student_regs[reg]}")

    mem_mismatches = []
    all_mem_addrs = set(prof_mem.keys()).union(set(student_mem.keys()))
    for addr in sorted(all_mem_addrs):
        prof_val = prof_mem.get(addr, None)
        student_val = student_mem.get(addr, None)
        if prof_val != student_val:
            mem_mismatches.append(f"Memory address {addr} mismatch: Expected {prof_val}, Got {student_val}")

    if not reg_mismatches and not mem_mismatches:
        student_res = {
            "name": name,
            "score": 1.0,
            "max_score": 1.0,
            "status": "passed",
            "output": "Pass"
        }
        instructor_detail = (
            f"Pass.\n"
            f"Correct registers: {student_regs}\n"
            f"Correct memory: {student_mem}"
        )
    else:
        details = []
        if reg_mismatches:
            details.append("Register Mismatches:\n" + "\n".join(reg_mismatches))
        if mem_mismatches:
            details.append("Memory Mismatches:\n" + "\n".join(mem_mismatches))
            
        output_details = "\n\n".join(details)
        student_res = {
            "name": name,
            "score": 0.0,
            "max_score": 1.0,
            "status": "failed",
            "output": "Fail"
        }
        instructor_detail = (
            f"Mismatch in results:\n\n{output_details}"
        )
        
    return student_res, instructor_detail


def main():
    # Identify student submission file
    student_file = find_student_submission()
    
    test_results = []
    instructor_logs = []
    
    if student_file is None:
        # Build failing results for all test cases if no file was found
        for tc in TEST_CASES:
            msg = "No student MIPS submission file (.asm or .asm.txt) was found in /autograder/submission/."
            test_results.append({
                "name": tc["name"],
                "score": 0.0,
                "max_score": 1.0,
                "status": "failed",
                "output": "Fail"
            })
            instructor_logs.append((tc["name"], msg))
    else:
        try:
            with open(student_file, "r", encoding="utf-8", errors="ignore") as f:
                student_code = f.read()
            
            # Grade each test case
            for tc in TEST_CASES:
                res, detail = grade_testcase(tc, student_code)
                test_results.append(res)
                instructor_logs.append((tc["name"], detail))
                
        except Exception as e:
            # General file read or processing error
            for tc in TEST_CASES:
                test_results.append({
                    "name": tc["name"],
                    "score": 0.0,
                    "max_score": 1.0,
                    "status": "failed",
                    "output": "Fail"
                })
                instructor_logs.append((tc["name"], f"Failed to read submission file: {str(e)}"))

    # Calculate final cumulative score
    total_score = round(sum(res["score"] for res in test_results), 2)
    
    results = {
        "score": total_score,
        "stdout_visibility": "hidden",
        "tests": test_results
    }
    
    # Write Gradescope JSON results
    results_dir = "/autograder/results"
    if not os.path.exists(results_dir):
        try:
            os.makedirs(results_dir, exist_ok=True)
        except Exception:
            # Fallback to local directory for debugging/local testing
            results_dir = "./results"
            os.makedirs(results_dir, exist_ok=True)
            
    results_path = os.path.join(results_dir, "results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)
        
    print("=================== INSTRUCTOR DETAILS ===================")
    for name, detail in instructor_logs:
        print(f"--- {name} ---")
        print(detail)
        print()
    print("==========================================================")
    
    print(f"Grading complete. Results written to {results_path}")
    print(f"Total Score: {total_score}/{len(TEST_CASES)}")


if __name__ == "__main__":
    main()
