// update.exe — 拾字 FontTuner 自动更新器
//
// 用法:
//
//	修复/手动更新:  双击 update.exe（自动扫描当前目录下的 v*.zip）
//	程序内自动更新:  update.exe --wait-pid <主程序PID>
//
// 行为:
//	  1) 扫描安装目录下所有 v*.zip，按版本号取最新
//	  2) 有本地 zip → 解压覆盖 script/ → 删除 zip
//	  3) 无本地 zip → 从 GitHub 拉取最新 Release
//	  4) 拉取失败 → 提示用户手动下载
//	  5) 完成后重启 FontTuner.exe
package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// 构建时注入
var version = "1.0.0"

func main() {
	waitPID := flag.Int("wait-pid", 0, "")
	showVer := flag.Bool("version", false, "")
	flag.Parse()

	if *showVer {
		fmt.Printf("FontTuner Updater v%s\n", version)
		return
	}

	// 自动检测安装目录：update.exe 所在目录
	installDir, err := func() (string, error) {
		exe, err := os.Executable()
		if err != nil {
			return "", err
		}
		return filepath.Dir(exe), nil
	}()
	if err != nil {
		fmt.Fprintf(os.Stderr, "错误: 无法获取程序路径: %v\n", err)
		os.Exit(1)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	code := DoUpdate(ctx, installDir, *waitPID)
	os.Exit(code.ExitCode())
}
