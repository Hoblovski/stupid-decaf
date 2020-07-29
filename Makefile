ANTLR_JAR=/home/hob/Programs/ta-courses/cp2020/src/neo-backend/exp/antlr-4.8-complete.jar

run: grammar
	python3 main.py input

grammar:
	java -jar $(ANTLR_JAR) -Dlanguage=Python3 -visitor -no-listener -o generated MiniDecaf.g4

clean:
	rm __pycache__ generated -rf


.PHONY: run FORCE grammar clean

FORCE:


