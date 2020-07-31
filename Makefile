ANTLR_JAR=/home/hob/Programs/ta-courses/cp2020/src/neo-backend/exp/antlr-4.8-complete.jar
CP=$(ANTLR_JAR):generated

all: run

gui:
	java -jar $(ANTLR_JAR) -o generated MiniDecaf.g4
	javac -cp $(CP) generated/*.java
	java -cp $(CP) org.antlr.v4.gui.TestRig MiniDecaf top -gui input

run: grammar
	python3 main.py input
	riscv64-unknown-elf-gcc output.s runtime.c
	qemu-riscv64 a.out ; echo [Command returned] $$?

gcc:
	riscv64-unknown-elf-gcc output.s runtime.c
	qemu-riscv64 a.out ; echo [Command returned] $$?

grammar:
	java -jar $(ANTLR_JAR) -Dlanguage=Python3 -visitor -listener -o generated MiniDecaf.g4

clean:
	rm __pycache__ generated output.s a.out -rf


.PHONY: run FORCE grammar clean all gui

FORCE:


