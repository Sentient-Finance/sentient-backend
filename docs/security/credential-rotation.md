# Credential Rotation Runbook

> Thực hiện checklist này **ngay lập tức** khi phát hiện credentials bị lộ trong chat, log, hoặc bất kỳ kênh không an toàn nào.

---

## Inventory – Toàn bộ Secrets của Project

| Secret Name | Nơi dùng | Nơi lưu | Rotate tại |
|---|---|---|---|
| `OPENCLAW_HOOK_URL` | `openclaw-bridge.yml` | GitHub Actions Secret | OpenClaw dashboard |
| `OPENCLAW_HOOK_TOKEN` | `openclaw-bridge.yml` | GitHub Actions Secret | OpenClaw dashboard |
| `GITHUB_TOKEN` | `openclaw-bridge.yml` | Auto-generated bởi GitHub | Không cần rotate |
| GitHub PAT (personal) | Git push/pull, gh CLI | Local `~/.gitconfig` / CI | github.com/settings/tokens |
| `ETH_RPC_URL` | Indexer / Web3 | `.env` (runtime) | RPC provider dashboard |
| `BASE_RPC_URL` | Indexer / Web3 | `.env` (runtime) | RPC provider dashboard |
| `ARBITRUM_RPC_URL` | Indexer / Web3 | `.env` (runtime) | RPC provider dashboard |
| `DEPLOY_PRIVATE_KEY` | Deploy scripts | `.env` (runtime) | Tạo ví mới + transfer funds |
| `POSTGRES_PASSWORD` | DB connection | `.env` / docker-compose | Chỉ cần rotate nếu DB exposed ra ngoài |

---

## Checklist Rotate – Step by Step

### 1. GitHub PAT (Personal Access Token)

- [ ] Vào https://github.com/settings/tokens
- [ ] Tìm token đã lộ → **Delete**
- [ ] Tạo token mới: **Fine-grained** (preferred) hoặc Classic
  - Scope tối thiểu: `Contents: Read & Write`, `Pull requests: Read & Write`, `Issues: Read & Write`
- [ ] Cập nhật token mới vào nơi đang dùng (local git credential, CI secret, v.v.)
- [ ] Verify: `git ls-remote origin` với token mới → OK

### 2. EVM Deploy Wallet Private Key

> **Ưu tiên cao nhất** – key lộ = funds có thể bị drain ngay lập tức.

- [ ] **Ngay lập tức**: Tạo ví mới
  ```bash
  # Dùng Foundry
  cast wallet new

  # Hoặc tạo bằng ethers.js / wagmi CLI
  ```
- [ ] Transfer toàn bộ native token (ETH, BASE, ARB) sang ví mới
- [ ] Transfer toàn bộ ERC-20 tokens sang ví mới
- [ ] Revoke token approvals của ví cũ (dùng revoke.cash hoặc etherscan)
- [ ] Cập nhật `DEPLOY_PRIVATE_KEY` trong `.env` và GitHub Secrets
- [ ] Cập nhật địa chỉ deployer trong infra/config nếu có whitelist

### 3. OpenClaw Webhook Token

- [ ] Vào OpenClaw dashboard → Webhook settings → **Regenerate token**
- [ ] Copy token mới

### 4. Cập nhật GitHub Actions Secrets

> Tại: GitHub repo → **Settings** → **Secrets and variables** → **Actions**

- [ ] Update `OPENCLAW_HOOK_TOKEN` → token mới từ bước 3
- [ ] Update `OPENCLAW_HOOK_URL` → nếu URL thay đổi
- [ ] Update `DEPLOY_PRIVATE_KEY` → key ví mới từ bước 2
- [ ] Update bất kỳ PAT-based secret nào → PAT mới từ bước 1

### 5. Cập nhật Runtime `.env`

- [ ] Mở `.env` trên server/VPS đang chạy
- [ ] Replace giá trị cũ → giá trị mới cho tất cả secrets đã rotate
- [ ] Restart services:
  ```bash
  docker compose down && docker compose up -d
  # hoặc
  systemctl restart sentient-api sentient-worker sentient-indexer
  ```

### 6. Xác nhận Token Cũ Đã Bị Revoke

- [ ] Test GitHub PAT cũ:
  ```bash
  curl -H "Authorization: Bearer <OLD_TOKEN>" https://api.github.com/user
  # Expect: 401 Unauthorized
  ```
- [ ] Test OpenClaw token cũ:
  ```bash
  curl -H "Authorization: Bearer <OLD_TOKEN>" "$OPENCLAW_HOOK_URL"
  # Expect: 401 Unauthorized
  ```

### 7. Verify Workflow Pass

- [ ] Trigger `openclaw-bridge.yml` thủ công:
  - GitHub repo → **Actions** → **OpenClaw GitHub Bridge** → **Run workflow**
- [ ] Job kết thúc **green** → token mới hoạt động ✅

---

## Verification Checklist (Done When)

- [ ] Token cũ trả `401` khi test thủ công
- [ ] `openclaw-bridge.yml` workflow_dispatch pass
- [ ] Không còn secret nào hardcode trong code (chạy scan bên dưới)
- [ ] File checklist này đã được commit vào repo

### Secret Scan (chạy trước khi commit)

```bash
# Scan toàn bộ repo, tìm patterns có vẻ là secret
git log --all --full-history -- '*.env' | head -20
grep -r "ghp_\|github_pat_\|xox\|sk-\|0x[0-9a-fA-F]\{64\}" . \
  --include="*.py" --include="*.yml" --include="*.yaml" \
  --include="*.json" --include="*.toml" \
  --exclude-dir=".git"
```

Nếu grep trả kết quả → xem xét ngay, có thể cần `git filter-repo` để purge khỏi history.

---

## Audit Log

| Ngày | Người thực hiện | Lý do | Secrets được rotate |
|---|---|---|---|
| <!-- YYYY-MM-DD --> | <!-- @handle --> | <!-- Leaked in chat/log/other --> | <!-- List secrets --> |

> Cập nhật bảng này mỗi lần rotate. Không ghi giá trị thực của secret, chỉ ghi tên biến.

---

## Phòng ngừa (Prevention)

- Không bao giờ paste secret vào chat, PR description, issue, hoặc commit message
- Luôn dùng `.env` (gitignored) cho local, GitHub Secrets cho CI
- Bật [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning/about-secret-scanning) cho repo
- Xem xét dùng [git-secrets](https://github.com/awslabs/git-secrets) hoặc [gitleaks](https://github.com/gitleaks/gitleaks) pre-commit hook
- Dùng Fine-grained PAT với expiry date thay vì classic PAT không expire
