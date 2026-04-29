# Verified Solution for ALU and Memory Ops
lw $t0, 0($s0)       # Load A[0]
lw $t1, 4($s0)       # Load A[1]

mult $t0, $t1
mflo $t2             # A[4]
mfhi $t3             # A[2]
sw $t2, 16($s0)
sw $t3, 8($s0)

addi $t5, $zero, 230
div $t2, $t5
mflo $t4             # A[5]
mfhi $t5             # a (Remainder)
sw $t4, 20($s0)

srl $t6, $t5, 16     # b = a >> 16
andi $t7, $t5, 8     # a & 8
ori $t8, $t6, 3      # b | 3
or $t7, $t7, $t8     # c = (a&8) | (b|3)
sll $t9, $t5, 2      # d = a << 2

# Concatenation into A[6] (address 24)
sh $t9, 24($s0)      # Store d (2 bytes)
sb $t7, 26($s0)      # Store c (1 byte)
sb $t6, 27($s0)      # Store b (1 byte)

# A[3] = (A[0] + A[1] - 100) - (A[2] + A[4] - A[5])
add $t5, $t0, $t1
addi $t5, $t5, -100
add $t6, $t3, $t2
sub $t6, $t6, $t4
sub $t6, $t5, $t6
sw $t6, 12($s0)      # Store A[3]
