# antlr-py

依赖
* [antlr 4.8](https://www.antlr.org/)
* python 3
* requirements.txt 里面所有依赖
* `riscv64-unknown-elf-gcc`, `qemu-riscv64`

运行（默认使用 input 文件当输入）
```bash
make
qemu-riscv64 a.out ; echo $?
```
