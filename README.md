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

变化
* assign 不是 expr
  - 除了 C 任何正常的语言都没这种鬼扯的设定
  - expr 除了 call 应该都是没有副作用的，这也就是为什么 python 里面没 ++ / --
  - `if (a=b)` 这种代码就不该出现
  - chain assignment 可以单独处理

* 去掉了 char 类型
  - 没有意义

* 函数只做了一种 variant -- 另一种的 spec 没看懂

注意
* 动态作用域
