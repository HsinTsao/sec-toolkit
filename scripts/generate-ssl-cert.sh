#!/bin/bash

# SSL 证书生成脚本
# 用于生成自签名证书，适用于开发和测试环境
# 生产环境建议使用 Let's Encrypt 或购买正式证书

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

print_info() { echo -e "${CYAN}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 默认配置
CERT_DIR="${1:-$(dirname "$0")/../certs}"
DOMAIN="${2:-localhost}"
DAYS="${3:-365}"

# 创建证书目录
mkdir -p "$CERT_DIR"

print_info "生成 SSL 证书..."
print_info "证书目录: $CERT_DIR"
print_info "域名: $DOMAIN"
print_info "有效期: $DAYS 天"

# 检查是否已存在证书
if [ -f "$CERT_DIR/server.key" ] && [ -f "$CERT_DIR/server.crt" ]; then
    print_warning "证书已存在!"
    echo -n "是否重新生成？[y/N] "
    read -r confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        print_info "保留现有证书"
        exit 0
    fi
fi

# 创建 OpenSSL 配置文件
cat > "$CERT_DIR/openssl.cnf" << EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_req

[dn]
C = CN
ST = Beijing
L = Beijing
O = Security Toolkit Dev
OU = Development
CN = ${DOMAIN}

[v3_req]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = ${DOMAIN}
DNS.2 = *.${DOMAIN}
DNS.3 = localhost
DNS.4 = *.localhost
IP.1 = 127.0.0.1
IP.2 = ::1
EOF

# 生成私钥
print_info "生成私钥..."
openssl genrsa -out "$CERT_DIR/server.key" 2048

# 生成证书签名请求 (CSR)
print_info "生成证书签名请求..."
openssl req -new -key "$CERT_DIR/server.key" \
    -out "$CERT_DIR/server.csr" \
    -config "$CERT_DIR/openssl.cnf"

# 生成自签名证书
print_info "生成自签名证书..."
openssl x509 -req -days "$DAYS" \
    -in "$CERT_DIR/server.csr" \
    -signkey "$CERT_DIR/server.key" \
    -out "$CERT_DIR/server.crt" \
    -extensions v3_req \
    -extfile "$CERT_DIR/openssl.cnf"

# 生成 PEM 格式（包含证书和私钥）
cat "$CERT_DIR/server.crt" "$CERT_DIR/server.key" > "$CERT_DIR/server.pem"

# 清理临时文件
rm -f "$CERT_DIR/server.csr" "$CERT_DIR/openssl.cnf"

# 设置权限
chmod 600 "$CERT_DIR/server.key"
chmod 644 "$CERT_DIR/server.crt"
chmod 600 "$CERT_DIR/server.pem"

print_success "SSL 证书生成完成！"
echo ""
echo "生成的文件:"
echo "  - 私钥:   $CERT_DIR/server.key"
echo "  - 证书:   $CERT_DIR/server.crt"
echo "  - PEM:    $CERT_DIR/server.pem"
echo ""

# macOS 信任证书提示
if [[ "$OSTYPE" == "darwin"* ]]; then
    print_info "macOS 用户：要信任此证书，请运行以下命令："
    echo ""
    echo "  sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain $CERT_DIR/server.crt"
    echo ""
    echo -n "是否现在添加信任？(需要管理员密码) [y/N] "
    read -r trust_confirm
    if [ "$trust_confirm" = "y" ] || [ "$trust_confirm" = "Y" ]; then
        sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain "$CERT_DIR/server.crt"
        print_success "证书已添加到系统钥匙串"
    fi
fi

# Linux 信任证书提示
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    print_info "Linux 用户：要信任此证书，请运行以下命令："
    echo ""
    echo "  # Ubuntu/Debian:"
    echo "  sudo cp $CERT_DIR/server.crt /usr/local/share/ca-certificates/security-toolkit.crt"
    echo "  sudo update-ca-certificates"
    echo ""
    echo "  # CentOS/RHEL:"
    echo "  sudo cp $CERT_DIR/server.crt /etc/pki/ca-trust/source/anchors/security-toolkit.crt"
    echo "  sudo update-ca-trust"
fi

echo ""
print_warning "注意：自签名证书仅用于开发测试，生产环境请使用正式证书！"

