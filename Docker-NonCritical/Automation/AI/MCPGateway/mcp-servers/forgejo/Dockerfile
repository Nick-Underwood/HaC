FROM golang:alpine AS builder
RUN apk add --no-cache git
WORKDIR /build
RUN git clone --depth 1 https://codeberg.org/goern/forgejo-mcp.git .
RUN go build -o forgejo-mcp .

FROM alpine:latest
RUN apk add --no-cache ca-certificates
COPY --from=builder /build/forgejo-mcp /usr/local/bin/forgejo-mcp
EXPOSE 3000
CMD ["forgejo-mcp", "--transport", "http", "--http-port", "3000"]
