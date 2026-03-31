"""
检查数据库中的工作流状态
"""
import asyncio
import aiosqlite

async def check_database():
    print("=" * 60)
    print("检查数据库内容")
    print("=" * 60)
    
    db_path = "epistemicflow.db"
    
    async with aiosqlite.connect(db_path) as db:
        # 检查所有表
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = await cursor.fetchall()
        print(f"\n数据库中的表: {[t[0] for t in tables]}")
        
        # 检查 workflow_states 表
        if ('workflow_states',) in tables:
            cursor = await db.execute("SELECT COUNT(*) FROM workflow_states")
            count = await cursor.fetchone()
            print(f"\nworkflow_states 表记录数: {count[0]}")
            
            if count[0] > 0:
                cursor = await db.execute("""
                    SELECT id, session_id, workflow_name, current_stage, status, 
                           created_at, updated_at, error_message
                    FROM workflow_states
                    ORDER BY created_at DESC
                    LIMIT 5
                """)
                rows = await cursor.fetchall()
                print("\n最近的工作流记录:")
                for row in rows:
                    print(f"  ID: {row[0]}")
                    print(f"    session_id: {row[1]}")
                    print(f"    workflow_name: {row[2]}")
                    print(f"    current_stage: {row[3]}")
                    print(f"    status: {row[4]}")
                    print(f"    created_at: {row[5]}")
                    print(f"    updated_at: {row[6]}")
                    print(f"    error_message: {row[7]}")
                    print()
        else:
            print("\nworkflow_states 表不存在")

asyncio.run(check_database())
