; ModuleID = "main"
target triple = "x86_64-unknown-linux-gnu"
target datalayout = ""

@"true" = constant i1 1
@"false" = constant i1 0
define i32 @"add"(i32 %".1", i32 %".2")
{
add_entry:
  %".4" = alloca i32
  store i32 %".1", i32* %".4"
  %".6" = alloca i32
  store i32 %".2", i32* %".6"
  %".8" = load i32, i32* %".4"
  %".9" = load i32, i32* %".6"
  %".10" = add i32 %".8", %".9"
  ret i32 %".10"
}

define i32 @"main"()
{
main_entry:
  %".2" = alloca i32
  store i32 5, i32* %".2"
  %".4" = load i32, i32* %".2"
  %".5" = icmp eq i32 %".4", 5
  br i1 %".5", label %"main_entry.if", label %"main_entry.else"
main_entry.if:
  %".7" = call i32 @"add"(i32 10, i32 5)
  ret i32 %".7"
main_entry.else:
  %".9" = call i32 @"add"(i32 10, i32 1)
  ret i32 %".9"
main_entry.endif:
  ret i32 0
}
