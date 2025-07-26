#!/usr/bin/env python3
"""Test that MCPHawk can capture both TCP and WebSocket traffic."""

import json
import sqlite3


def check_captured_messages():
    """Check the MCPHawk database for captured messages."""
    try:
        conn = sqlite3.connect("mcphawk_logs.db")
        cursor = conn.cursor()

        # Get total count
        cursor.execute("SELECT COUNT(*) FROM logs")
        total = cursor.fetchone()[0]
        print(f"Total messages in database: {total}")

        # Check TCP messages (port 12345)
        cursor.execute("""
            SELECT COUNT(*) FROM logs
            WHERE (src_port = 12345 OR dst_port = 12345)
            AND message LIKE '%jsonrpc%'
        """)
        tcp_count = cursor.fetchone()[0]
        print(f"TCP MCP messages (port 12345): {tcp_count}")

        # Check WebSocket messages (port 8765)
        cursor.execute("""
            SELECT COUNT(*) FROM logs
            WHERE (src_port = 8765 OR dst_port = 8765)
            AND message LIKE '%jsonrpc%'
        """)
        ws_count = cursor.fetchone()[0]
        print(f"WebSocket MCP messages (port 8765): {ws_count}")

        # Show sample messages
        if tcp_count > 0:
            print("\nSample TCP messages:")
            cursor.execute("""
                SELECT message FROM logs
                WHERE (src_port = 12345 OR dst_port = 12345)
                AND message LIKE '%jsonrpc%'
                LIMIT 3
            """)
            for row in cursor:
                msg = json.loads(row[0])
                print(f"  - {msg.get('method', msg.get('result', '?'))}")

        if ws_count > 0:
            print("\nSample WebSocket messages:")
            cursor.execute("""
                SELECT message FROM logs
                WHERE (src_port = 8765 OR dst_port = 8765)
                AND message LIKE '%jsonrpc%'
                LIMIT 3
            """)
            for row in cursor:
                msg = json.loads(row[0])
                print(f"  - {msg.get('method', msg.get('result', '?'))}")

        conn.close()

        # Summary
        print("\n" + "="*50)
        if tcp_count > 0 and ws_count > 0:
            print("✅ SUCCESS: Both TCP and WebSocket MCP traffic captured!")
        elif tcp_count > 0:
            print("⚠️  Only TCP traffic captured")
        elif ws_count > 0:
            print("⚠️  Only WebSocket traffic captured")
        else:
            print("❌ No MCP traffic captured")

    except Exception as e:
        print(f"Error checking database: {e}")


if __name__ == "__main__":
    print("MCPHawk Capture Test")
    print("="*50)
    print("\nChecking captured messages...")
    print("(Make sure MCPHawk is running and traffic has been generated)\n")

    check_captured_messages()

