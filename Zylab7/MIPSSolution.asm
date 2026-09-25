# A - $s0, B - $s1, n - $s2

Main:    addi $t1, $zero, 0   # j = 0
Loop1:   bge $t0, $s2, Exit   # j >= n exit
         sll $t1, $t0, 2      # j * 4
         add $t1, $t1, $s1    # Address of B[j]
         addi $a0, $s0, 0     # 1st argument to function
         addi $a1, $t0, 0     # 2nd argument to function
         jal nSum             # Call function
         sw $v0, 0($t1)       # Write to B[j]
         addi $t0, $t0, 1     # j ++
         j Loop1               
      
nSum:    lw $v0, 0($a0)       # sum = A[0]
         addi $t2, $zero, 1      # j = 1
Loop2:   bgt $t2, $a1, End    # j > k end
         sll $t3, $t2, 2      # j * 4
         add $t3, $t3, $a0    # address of A[j]
         lw $t3, 0($t3)       # value of A[j]
         add $v0, $v0, $t3    # sum += A[j]
         addi $t2, $t2, 1     # j ++
         j Loop2 
End:     jr $ra

Exit: