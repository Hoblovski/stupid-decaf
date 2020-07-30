ANTLR_JAR=/home/hob/Programs/ta-courses/cp2020/src/neo-backend/exp/antlr-4.8-complete.jar

run: grammar
	python3 main.py input
	python3 main.py input > output.s
	riscv64-unknown-elf-gcc output.s
	qemu-riscv64 a.out ; echo $$?

grammar:
	java -jar $(ANTLR_JAR) -Dlanguage=Python3 -visitor -listener -o generated MiniDecaf.g4

clean:
	rm __pycache__ generated output.s a.out -rf


.PHONY: run FORCE grammar clean

FORCE:


