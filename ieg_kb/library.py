from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List

from .config import library_path


TAXONOMY = [
    "00_待分类",
    "01_投标报价/01_招标文件与澄清",
    "01_投标报价/02_工程量清单与估算",
    "01_投标报价/03_询价与分包报价",
    "01_投标报价/04_价格库与费率",
    "01_投标报价/05_投标策略与复盘",
    "02_技术方案/01_施工组织",
    "02_技术方案/02_专项方案",
    "02_技术方案/03_临建与物流",
    "02_技术方案/04_设备材料",
    "02_技术方案/05_标准规范",
    "03_工效与资源/01_工效定额",
    "03_工效与资源/02_人工",
    "03_工效与资源/03_机械",
    "03_工效与资源/04_进度计划",
    "03_工效与资源/05_气候与日历",
    "04_风险与HSE/01_国别风险",
    "04_风险与HSE/02_项目风险",
    "04_风险与HSE/03_HSE",
    "04_风险与HSE/04_保险与担保",
    "04_风险与HSE/05_风险复盘",
    "05_合同与索赔/01_合同条件",
    "05_合同与索赔/02_FIDIC与范本",
    "05_合同与索赔/03_合同评审",
    "05_合同与索赔/04_变更索赔",
    "05_合同与索赔/05_通知与函件",
    "05_合同与索赔/06_争议解决",
    "06_国别与市场/01_法律税务",
    "06_国别与市场/02_劳工与签证",
    "06_国别与市场/03_汇率与金融",
    "06_国别与市场/04_供应链与市场价",
    "06_国别与市场/05_文化与利益相关方",
    "07_项目案例与复盘/01_在建项目",
    "07_项目案例与复盘/02_完工项目",
    "07_项目案例与复盘/03_经验教训",
    "08_标准规范/01_国际标准",
    "08_标准规范/02_业主标准",
    "08_标准规范/03_当地标准",
    "09_模板与清单/01_投标",
    "09_模板与清单/02_技术",
    "09_模板与清单/03_合同",
    "09_模板与清单/04_风险",
    "09_模板与清单/05_复盘",
    "90_参考书籍",
    "99_归档",
]


def initialize_library(config: Dict[str, Any]) -> List[str]:
    root = library_path(config)
    created = []
    for relative in TAXONOMY:
        path = root / relative
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(str(path))
    examples = Path(config["_root"]) / "examples" / "library"
    if examples.exists():
        for source in examples.rglob("*"):
            if not source.is_file():
                continue
            target = root / source.relative_to(examples)
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    return created
