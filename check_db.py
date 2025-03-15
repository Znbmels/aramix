import asyncio
import aiomysql
import logging

#логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#базы данных
DB_CONFIG = {
    "host": "crm.aramax.kz",  
    "port": 3306,             
    "user": "bn_suitecrm",    
    "password": "bitnami123", 
    "db": "aramax",           
}

async def get_db_connection():
#Устанавливает соединение с базой данных.
    try:
        pool = await aiomysql.create_pool(**DB_CONFIG)
        logger.info("Подключение к базе данных успешно установлено.")
        return pool
    except Exception as e:
        logger.error(f"Ошибка при подключении к базе данных: {e}")
        raise

async def get_table_structure():
#Проверяет структуру таблицы u_bot.

    pool = await get_db_connection()
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "DESCRIBE u_bot"
                logger.info(f"Выполняется запрос: {query}")
                await cursor.execute(query)
                result = await cursor.fetchall()
                logger.info("Структура таблицы u_bot:")
                for row in result:
                    logger.info(row)
                return result
    except Exception as e:
        logger.error(f"Ошибка при получении структуры таблицы: {e}")
    finally:
        pool.close()
        await pool.wait_closed()

async def main():

#Основная функция.

    await get_table_structure()

if __name__ == "__main__":
    asyncio.run(main())
