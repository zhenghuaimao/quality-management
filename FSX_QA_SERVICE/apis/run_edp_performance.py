# -*- coding:utf-8 -*-
import json
import os
import shutil
import subprocess
import zipfile
import time
import random
import tempfile
from flask_cors import CORS
from datetime import datetime
from FSX_QA_SERVICE.apis.Application import global_connection_pool
from flask_jwt_extended import jwt_required
from flask import send_file, Response, request, jsonify, Blueprint, make_response, stream_with_context
app_run_edp_performance = Blueprint("run_edp_performance", __name__)
CORS(app_run_edp_performance, supports_credentials=True)


# 生成TaskId
def get_task_id():
    taskid = 1
    # 获取当前时间并且进行格式转换
    t = int(time.time())
    str1 = ''.join([str(i) for i in random.sample(range(0, 9), 2)])
    return str(t) + str1 + str(taskid).zfill(2)


# 避免重复代码
def process_row(row):
    # 将 datetime 对象 row['CreateTime'] 格式化为 %Y-%m-%d %H:%M:%S 的时间字符串
    formatted_create_time = row['createTime'].strftime("%Y-%m-%d %H:%M:%S")
    return {
        "createTime": formatted_create_time,
        "source": row["createUser"],
        "status": row["status"],
        "taskId": row["taskId"]
    }


# 日志压缩
def create_zip_archive(file_paths, zip_file_path):
    with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in file_paths:
            zipf.write(file_path, os.path.basename(file_path))


def tst(data):
    # 判空处理
    if not data or data == b'':
        yield jsonify({"error": "Invalid request data"}), 400
        return
        # return或者直接执行默认参数
    # 数据转换
    datas = json.loads(data)

    task_id = get_task_id()
    creator = datas["source"]
    create_time = datetime.now().isoformat()

    # 创建一个空数组用于存放shell命令
    commands = []
    # 循环从请求体中将shell命令读取出来
    for command in datas["commands"]:
        shell = command["value"] + " --TaskId {}".format(task_id) + " &\n" + "sleep 1\n"
        commands.append(shell)
    try:
        # 格式化数组中的shell命令
        shell_commands = ''.join(commands)
        # 将shell_commands用Popen方法执行
        process = subprocess.Popen(shell_commands, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # 读取process子进程的执行结果，poll方法执行时，如果子进程未结束，则返回None
        result = process.poll()
        if result is None:
            result = "progressing"
            # 先将压力测试任务创建成功返回给接口，然后继续等待压力测试脚本执行结果
            insert_performance_record(task_id, creator, result)
            response = {
                'creator': creator,
                'taskId': task_id,
                'status': result,
                'createTime': create_time,
                'type': 1
            }
            yield 'data: {}\n\n'.format(json.dumps(response))

        # 创建两个空数组用来存放shell命令的执行结果（status）还有执行输出（outputs）
        statuses = []
        outputs = []
        process.wait()
        result = "completed"
        status = process.returncode
        outputs_stdout, outputs_stderr = process.communicate()
        statuses.append(status)
        outputs.append((outputs_stdout, outputs_stderr))

    except subprocess.CalledProcessError as e:
        output = e.stderr.strip()
        result = "error"
        response = {
            "result": result,
            "error": str(e),
            "output": output
        }
        return response
    #     修改成return之后没有调试

    except subprocess.TimeoutExpired:
        output = "Execution time out"
        result = "error"
        response = {
            "result": result,
            "error": "TimeoutExpired",
            "output": output
        }
        return response
        #     修改成return之后没有调试
    update_performance_record(task_id, result)
    response = {
        'creator': creator,
        'taskId': task_id,
        'status': result,
        'type': 1
    }
    yield 'data: {}\n\n'.format(json.dumps(response))


# 向PerformanceRecord插入数据
def insert_performance_record(task_id, creator, status):
    # 从数据库池获取数据库连接
    connection = global_connection_pool.connection()
    # 创建游标
    cursor = connection.cursor()

    # 构建SQL语句
    sql = "INSERT INTO `PerformanceRecord` (`taskId`, `type`, `createUser`, `status`) " \
          "VALUES (%s, %s, %s, %s)"
    values = (task_id, 1, creator, status)

    try:
        cursor.execute(sql, values)
        connection.commit()
    except Exception as e:
        print("Error while inserting into the database:", e)
        return jsonify({"error": str(e)})
    finally:
        cursor.close()
        connection.close()


def update_performance_record(task_id, status):
    # 从数据库池获取数据库连接
    connection = global_connection_pool.connection()
    # 创建游标
    cursor = connection.cursor()
    # 构建sql语句
    sql = "UPDATE `PerformanceRecord` SET `status`  = %s WHERE `taskId` = %s"
    values = (status, task_id)
    try:
        cursor.execute(sql, values)
        connection.commit()
    except Exception as e:
        print("Error while updating the database:", e)
        raise
    finally:
        cursor.close()
        connection.close()
    response = {
        'taskId': task_id,
        'status': status,
        'type': 1
    }
    return response


@app_run_edp_performance.route('/api/edp_performance_list/run_edp_performance', methods=['POST'])
@jwt_required()
def run_edp_performance():
    # 从请求体中获取数据
    data = request.get_data()
    # 判空处理
    if not data or data == b'':
        return jsonify({"error": "Invalid request data"}), 400
    headers = {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive'
    }

    # 将生成器转换为响应对象，并传递响应头
    return Response(stream_with_context(tst(data)), headers=headers)


@app_run_edp_performance.route('/api/edp_performance_list/download_performance_logs', methods=['GET'])
@jwt_required()
def download_performance_log_file():
    # 唯一参数时taskid，edp_performance_client脚本中需要将日志文件绑定taskid，然后再将其下载
    data = request.args.to_dict()
    # 判断传参是否为空
    if data is None or data == '':
        return jsonify({"Error": "Invalid file path"}), 400

    # 创建一个空数组用于存放所有日志的路径
    file_paths = []
    taskid = data["taskId"]
    # 日志地址
    log_path = "edp_fix_client/initiator/edp_performance_test/report"
    # 遍历日志目录下的所有文件
    for filename in os.listdir(log_path):
        if taskid in filename:
            log_filepath = os.path.join(log_path, filename)
            file_paths.append(log_filepath)
    if not file_paths:
        return jsonify({"Error": "The file is not found"}), 404
    # 创建临时目录用于存放压缩文件
    temp_dir = tempfile.mkdtemp()

    # 记录打包时间
    zip_time = datetime.now()
    zip_name = "performance_logs_{}.zip".format(zip_time.strftime("%Y-%m-%d_%H-%M-%S"))
    zip_file_path = os.path.join(temp_dir, zip_name)
    # 创建压缩文件
    create_zip_archive(file_paths, zip_file_path)

    # 创建响应对象
    response = make_response(send_file(zip_file_path, as_attachment=True))

    # 设置 Content-Disposition 头部字段
    response.headers['Content-Disposition'] = 'attachment; filename={}'.format(zip_name)

    # 删除临时目录及其内容
    shutil.rmtree(temp_dir)

    return response, 200


@app_run_edp_performance.route('/api/edp_performance_list', methods=['GET'])
@jwt_required()
def edp_performance_list():
    connection = global_connection_pool.connection()
    cursor = connection.cursor()
    data = request.args.to_dict()
    if data is not None and data != '':
        # if 'pageSize' in data and data['pageSize'] != "":
        #     str_pageSize = data["pageSize"]
        #     pageSize = int(str_pageSize)
        # else:
        #     pageSize = 10
        #
        # if 'current' in data and data['current'] != "":
        #     str_current = data["current"]
        #     current = int(str_current)
        # else:
        #     current = 1
        sql = ""
        if "source" in data and data["source"] != "":
            sql += " AND `createUser` = '{}'".format(data["source"])
        if "status" in data and data["status"] != "":
            sql += " AND `status` = '{}'".format(data["status"])
        if "createTime" in data and data["createTime"] != "":
            sql += " AND `createTime` LIKE '%{}%'".format(data["createTime"])
        if "taskId" in data and data["taskId"] != "":
            sql += " AND `taskId` LIKE '%{}%'".format(data["taskId"])
        sql = sql + ' ORDER BY `createTime` DESC'
        try:
            # 统计数据总数
            cursor.execute('SELECT COUNT(*) as total_count FROM `qa_admin`.PerformanceRecord '
                           'WHERE `type` = 1 {}'.format(sql))
            total_count = cursor.fetchone()["total_count"]
            # 查询数据
            cursor.execute("SELECT * FROM `qa_admin`.PerformanceRecord WHERE `type` = 1 {}".format(sql))
            search_result = cursor.fetchall()
            data = [process_row(row) for row in search_result]
            response = {
                "total_count": total_count,
                "data": data
            }
            return jsonify(response), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        finally:
            cursor.close()
            connection.close()
    else:
        try:
            # 统计数据总数
            count_sql = "SELECT COUNT(*) as total_count FROM `qa_admin`.PerformanceRecord WHERE `type` = 1;"
            cursor.execute(count_sql)
            total_count = cursor.fetchone()["total_count"]
            # 查询数据
            data_sql = "SELECT `createDate`, `status`, `createUser`, `taskId` " \
                       "FROM `qa_admin`.PerformanceRecord " \
                       "WHERE `type` = 1;"
            cursor.execute(data_sql)
            rows = cursor.fetchall()
            data = []
            for row in rows:
                data.append(
                    {
                        "taskId": row["taskId"],
                        "createTime": row["createDate"],
                        "source": row["createUser"],
                        "status": row["status"]
                    }
                )
            response = {
                'total_count': total_count,
                'data': data
            }
            return jsonify(response), 200
        except Exception as e:
            return jsonify({"Error": str(e)}), 500
        finally:
            cursor.close()
            connection.close()
