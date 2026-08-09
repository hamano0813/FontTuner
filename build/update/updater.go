// updater — 更新核心逻辑：GitHub API、下载、解压、重启
package main

import (
	"archive/zip"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

// ---------- Windows 代理检测 ----------

func getWindowsProxy() string {
	// 1) 优先取环境变量
	if p := os.Getenv("HTTPS_PROXY"); p != "" {
		return p
	}
	if p := os.Getenv("HTTP_PROXY"); p != "" {
		return p
	}
	if p := os.Getenv("https_proxy"); p != "" {
		return p
	}
	if p := os.Getenv("http_proxy"); p != "" {
		return p
	}
	// 2) 读取 Windows 系统代理设置（reg.exe）
	enable, _ := exec.Command("reg", "query",
		`HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings`,
		"/v", "ProxyEnable").Output()
	if !strings.Contains(string(enable), "0x1") {
		return ""
	}
	out, err := exec.Command("reg", "query",
		`HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings`,
		"/v", "ProxyServer").Output()
	if err != nil {
		return ""
	}
	lines := strings.Split(string(out), "\r\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "ProxyServer") {
			parts := strings.Split(line, "REG_SZ")
			if len(parts) == 2 {
				return strings.TrimSpace(parts[1])
			}
			parts = strings.Split(line, "REG_EXPAND_SZ")
			if len(parts) == 2 {
				return strings.TrimSpace(parts[1])
			}
		}
	}
	return ""
}

func proxyAwareHTTPClient() *http.Client {
	proxyURL := getWindowsProxy()
	if proxyURL == "" {
		return http.DefaultClient
	}
	// 确保有 scheme
	if !strings.Contains(proxyURL, "://") {
		proxyURL = "http://" + proxyURL
	}
	p, err := url.Parse(proxyURL)
	if err != nil {
		return http.DefaultClient
	}
	return &http.Client{
		Transport: &http.Transport{
			Proxy: http.ProxyURL(p),
		},
	}
}

// ---------- GitHub API 类型 ----------

type ghRelease struct {
	TagName string   `json:"tag_name"`
	Assets  []ghLink `json:"assets"`
}

type ghLink struct {
	Name               string `json:"name"`
	BrowserDownloadURL string `json:"browser_download_url"`
}

// ---------- 版本号 ----------

type semVer [3]int

func parseVer(s string) (semVer, bool) {
	s = strings.TrimPrefix(s, "v")
	parts := strings.SplitN(s, ".", 3)
	if len(parts) != 3 {
		return semVer{}, false
	}
	var v semVer
	for i, p := range parts {
		n, err := strconv.Atoi(p)
		if err != nil {
			return semVer{}, false
		}
		v[i] = n
	}
	return v, true
}

func (a semVer) newerThan(b semVer) bool {
	for i := range a {
		if a[i] != b[i] {
			return a[i] > b[i]
		}
	}
	return false
}

// ---------- GitHub API ----------

const ghReleaseURL = "https://api.github.com/repos/%s/releases/latest"

// FontTuner 的 GitHub 仓库（在线自动更新源）
const ghRepo = "hamano0813/FontTuner"

func fetchLatestRelease(ctx context.Context, repo string) (*ghRelease, error) {
	url := fmt.Sprintf(ghReleaseURL, repo)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("创建请求失败: %w", err)
	}
	req.Header.Set("Accept", "application/json")

	resp, err := proxyAwareHTTPClient().Do(req)
	if err != nil {
		return nil, fmt.Errorf("网络请求失败: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 512))
		return nil, fmt.Errorf("GitHub API 返回 %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}

	var rel ghRelease
	if err := json.NewDecoder(resp.Body).Decode(&rel); err != nil {
		return nil, fmt.Errorf("解析响应失败: %w", err)
	}

	if rel.TagName == "" {
		return nil, fmt.Errorf("响应中未找到版本信息")
	}

	return &rel, nil
}

func findZipAsset(rel *ghRelease, tag string) (*ghLink, bool) {
	want := tag + ".zip"
	for _, a := range rel.Assets {
		// 也接受不含 v 前缀的匹配
		if a.Name == want || a.Name == strings.TrimPrefix(want, "v") ||
			strings.EqualFold(a.Name, want) {
			return &a, true
		}
	}
	// 容错：找第一个 .zip asset
	for _, a := range rel.Assets {
		if strings.HasSuffix(strings.ToLower(a.Name), ".zip") {
			return &a, true
		}
	}
	return nil, false
}

// ---------- 下载 ----------

func downloadFile(ctx context.Context, url, dst string, prog func(done, total int64)) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return err
	}

	resp, err := proxyAwareHTTPClient().Do(req)
	if err != nil {
		return fmt.Errorf("下载失败: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("下载返回 %d", resp.StatusCode)
	}

	total := resp.ContentLength
	out, err := os.Create(dst)
	if err != nil {
		return fmt.Errorf("创建临时文件失败: %w", err)
	}
	defer out.Close()

	written := int64(0)
	buf := make([]byte, 32*1024)
	for {
		n, rErr := resp.Body.Read(buf)
		if n > 0 {
			if _, wErr := out.Write(buf[:n]); wErr != nil {
				return fmt.Errorf("写入失败: %w", wErr)
			}
			written += int64(n)
			if prog != nil {
				prog(written, total)
			}
		}
		if rErr == io.EOF {
			break
		}
		if rErr != nil {
			return fmt.Errorf("读取响应失败: %w", rErr)
		}
	}

	return nil
}

// ---------- ZIP 解压 ----------

func extractScriptZip(src, destDir string) error {
	r, err := zip.OpenReader(src)
	if err != nil {
		return fmt.Errorf("打开压缩包失败: %w", err)
	}
	defer r.Close()

	for _, f := range r.File {
		var target string
		if strings.HasPrefix(f.Name, "script/") || strings.HasPrefix(f.Name, "script\\") {
			rel := strings.TrimPrefix(strings.TrimPrefix(f.Name, "script/"), "script\\")
			if rel == "" {
				continue
			}
			target = filepath.Join(destDir, "script", rel)
		} else {
			if f.FileInfo().IsDir() {
				continue
			}
			target = filepath.Join(destDir, f.Name)
		}

		if f.FileInfo().IsDir() {
			if err := os.MkdirAll(target, 0755); err != nil {
				return fmt.Errorf("创建目录失败 %s: %w", target, err)
			}
			continue
		}

		if err := os.MkdirAll(filepath.Dir(target), 0755); err != nil {
			return fmt.Errorf("创建目录失败 %s: %w", filepath.Dir(target), err)
		}

		rc, err := f.Open()
		if err != nil {
			return fmt.Errorf("打开压缩包内文件失败 %s: %w", f.Name, err)
		}

		out, err := os.Create(target)
		if err != nil {
			rc.Close()
			return fmt.Errorf("创建文件失败 %s: %w", target, err)
		}

		_, err = io.Copy(out, rc)
		rc.Close()
		out.Close()
		if err != nil {
			return fmt.Errorf("解压文件失败 %s: %w", target, err)
		}
	}

	return nil
}

// ---------- 进程等待 ----------

func waitProcess(pid int) error {
	p, err := os.FindProcess(pid)
	if err != nil {
		return fmt.Errorf("找不到进程 %d: %w", pid, err)
	}
	_, err = p.Wait()
	return err
}

// ---------- 重启 ----------

func restartApp(appPath string) error {
	cmd := exec.Command(appPath)
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("启动主程序失败: %w", err)
	}
	return nil
}

// ---------- 本地更新包扫描 ----------

type zipFile struct {
	path    string
	version semVer
}

func scanLocalZips(dir string) []zipFile {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil
	}
	var result []zipFile
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		name := e.Name()
		// 匹配 v0.x.x.zip 格式
		if !strings.HasPrefix(name, "v") || !strings.HasSuffix(name, ".zip") {
			continue
		}
		verStr := strings.TrimSuffix(name, ".zip")
		v, ok := parseVer(verStr)
		if !ok {
			continue
		}
		result = append(result, zipFile{
			path:    filepath.Join(dir, name),
			version: v,
		})
	}
	return result
}

func pickLatestZip(files []zipFile) *zipFile {
	if len(files) == 0 {
		return nil
	}
	best := &files[0]
	for i := 1; i < len(files); i++ {
		if files[i].version.newerThan(best.version) {
			best = &files[i]
		}
	}
	return best
}

// ---------- 版本文件 ----------

func readVersionFile(dir string) (semVer, bool) {
	data, err := os.ReadFile(filepath.Join(dir, "version"))
	if err != nil {
		return semVer{}, false
	}
	return parseVer(strings.TrimSpace(string(data)))
}

// ---------- 更新主流程 ----------

// UpdateResult 描述更新结果
type UpdateResult int

const (
	ResultOK       UpdateResult = 0
	ResultError    UpdateResult = 1
	ResultNetError UpdateResult = 2
)

func (r UpdateResult) ExitCode() int { return int(r) }

// DoUpdate 执行更新。
//
//	installDir: 安装目录（含 version 文件和 FontTuner.exe）
//	waitPID:    >0 时先等该进程退出再操作（内部自动更新用）
func DoUpdate(ctx context.Context, installDir string, waitPID int) UpdateResult {
	fmt.Println("═══════════════════════════════════════")
	fmt.Println("  拾字 FontTuner — 自动更新")
	fmt.Println("═══════════════════════════════════════")

	// --- 等待主进程退出 ---
	if waitPID > 0 {
		fmt.Printf("⏳ 等待主程序退出 (PID %d)...\n", waitPID)
		time.Sleep(500 * time.Millisecond)
		if err := waitProcess(waitPID); err != nil {
			fmt.Fprintf(os.Stderr, "⚠ 等待主进程失败: %v\n", err)
		}
		fmt.Println("✓ 主程序已退出")
	}

	// --- 读取当前版本 ---
	currentVer, hasVer := readVersionFile(installDir)
	if !hasVer {
		fmt.Fprintln(os.Stderr, "✗ 未找到版本文件 (version)，请确认运行目录正确")
		fmt.Fprintln(os.Stderr, "  当前目录:", installDir)
		promptEnter()
		return ResultError
	}
	fmt.Printf("📌 当前版本: v%d.%d.%d\n", currentVer[0], currentVer[1], currentVer[2])

	// --- 先看本地有没有更新包 ---
	zips := scanLocalZips(installDir)
	if best := pickLatestZip(zips); best != nil && best.version.newerThan(currentVer) {
		fmt.Printf("📦 使用本地更新包: v%d.%d.%d\n",
			best.version[0], best.version[1], best.version[2])
		result := applyUpdate(ctx, best.path, installDir)
		if result == ResultOK {
			os.Remove(best.path)
		}
		promptEnter()
		return result
	}

	// --- 检查 GitHub 最新版本 ---
	rel, err := fetchLatestRelease(ctx, ghRepo)
	fmt.Printf("🌐 检查 GitHub 更新...\n")
	if err != nil {
		fmt.Fprintf(os.Stderr, "✗ 检查更新失败: %v\n", err)
		fmt.Fprintln(os.Stderr, "  请确认网络连接正常，或自行下载升级包")
		fmt.Fprintln(os.Stderr, "  下载地址: https://github.com/hamano0813/FontTuner/releases/latest")
		promptEnter()
		return ResultNetError
	}

	latestVer, ok := parseVer(rel.TagName)
	if !ok {
		fmt.Fprintf(os.Stderr, "✗ 无法解析最新版本号: %s\n", rel.TagName)
		promptEnter()
		return ResultError
	}
	fmt.Printf("📦 最新版本: %s\n", rel.TagName)

	// --- 版本比较 ---
	if !latestVer.newerThan(currentVer) {
		fmt.Println("✅ 当前已是最新版本")
		promptEnter()
		return ResultOK
	}

	// --- 发现新版本，自动下载 ---
	fmt.Printf("🔔 发现新版本 v%d.%d.%d，开始更新\n",
		latestVer[0], latestVer[1], latestVer[2])

	asset, ok := findZipAsset(rel, rel.TagName)
	if !ok {
		fmt.Fprintf(os.Stderr, "✗ 在发布页中未找到 %s.zip\n", rel.TagName)
		promptEnter()
		return ResultError
	}
	fmt.Printf("⏬ 下载更新包: %s\n", asset.Name)

	tmpDir, err := os.MkdirTemp("", "fonttuner-update-*")
	if err != nil {
		fmt.Fprintf(os.Stderr, "✗ 创建临时目录失败: %v\n", err)
		promptEnter()
		return ResultError
	}
	defer os.RemoveAll(tmpDir)

	tmpZip := filepath.Join(tmpDir, asset.Name)
	if err := downloadFile(ctx, asset.BrowserDownloadURL, tmpZip, func(done, total int64) {
		if total > 0 {
			pct := done * 100 / total
			fmt.Printf("\r  %d / %d KB (%d%%)", done/1024, total/1024, pct)
		} else {
			fmt.Printf("\r  %d KB", done/1024)
		}
	}); err != nil {
		fmt.Fprintf(os.Stderr, "\n✗ 下载失败: %v\n", err)
		fmt.Fprintln(os.Stderr, "  请自行下载升级包:")
		fmt.Fprintln(os.Stderr, "  https://github.com/hamano0813/FontTuner/releases/latest")
		promptEnter()
		return ResultNetError
	}
	fmt.Println("\n✓ 下载完成")

	return applyUpdate(ctx, tmpZip, installDir)
}

// applyUpdate 解压 zip → 重启主程序
func applyUpdate(_ context.Context, zipPath, installDir string) UpdateResult {
	fmt.Println("⏳ 等待主程序完全退出...")
	time.Sleep(3 * time.Second)
	fmt.Print("📂 解压中...\n")
	if err := extractScriptZip(zipPath, installDir); err != nil {
		fmt.Fprintf(os.Stderr, "\n✗ 解压失败: %v\n", err)
		promptEnter()
		return ResultError
	}
	fmt.Println("✓ 更新文件已安装")

	appPath := filepath.Join(installDir, "FontTuner.exe")
	if _, err := os.Stat(appPath); err == nil {
		fmt.Println("🚀 重新启动主程序...")
		if err := restartApp(appPath); err != nil {
			fmt.Fprintf(os.Stderr, "⚠ 启动主程序失败: %v\n", err)
			fmt.Println("  你可以手动启动 FontTuner.exe")
		}
	} else {
		fmt.Println("  未找到 FontTuner.exe，请手动启动程序")
	}

	fmt.Println("✅ 更新完成")
	return ResultOK
}

// promptEnter 等待用户按 Enter 退出
func promptEnter() {
	fmt.Print("按 Enter 键退出...")
	fmt.Scanln()
}
