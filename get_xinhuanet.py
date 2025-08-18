from bs4 import BeautifulSoup
import requests

def get_xinhuanet(lists=3):
    if lists not in [1, 2, 3]:
        return "lists参数错误，请输入1、2或3。"
    
    url = ("http://news.cn/")
    try:
        response = requests.get(url)
        response.raise_for_status()  # 检查请求是否成功
        html_content = response.text
    except requests.exceptions.RequestException as e:
        return f"请求失败: {e}"

    # 创建BeautifulSoup对象
    soup = BeautifulSoup(html_content, 'html.parser')

    # 存储结果
    result = "以下为新华网的新闻标题："

    # 1. 提取headline部分的新闻
    headline_div = soup.find('div', id='headline')
    if headline_div:
        result += "\n\n### 头条新闻"
        for a_tag in headline_div.select('.part.bg-white a'):
            url = a_tag.get('href', '')
            title = a_tag.get_text(strip=True)
            if url and title:
                result += f"\n- [{title}]({url})"
    if lists == 1:
        return result
                

    # 2. 提取focusListNews部分的新闻
    focus_div = soup.find('div', id='focusListNews')
    if focus_div:
        result += "\n\n### 次头条新闻"
        for li in focus_div.find_all('li'):
            result += "\n- "
            # 处理每个li中的多个a标签
            for a_tag in li.find_all('a'):
                url = a_tag.get('href', '')
                title = a_tag.get_text(strip=True)
                if url and title:
                    result += f"[{title}]({url}) "
    if lists == 2:
        return result

    # 3. 提取depth-cont部分的新闻
    depth_cont_div = soup.find('div', id='depth')
    if depth_cont_div:
        result += "\n\n### 其他要闻"
        depth_cont = depth_cont_div.select_one('.part.bg-white .depth-cont')
        if depth_cont:
            # 提取所有list-txt dot下的链接
            for list_div in depth_cont.select('.list.list-txt.dot'):
                for li in list_div.find_all('li'):
                    result += "\n- "
                    for a_tag in li.find_all('a'):
                        url = a_tag.get('href', '')
                        title = a_tag.get_text(strip=True)
                        if url and title:
                            result += f"[{title}]({url}) "
    return result

if __name__ == "__main__":
    print(get_xinhuanet())
