const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, PageNumber, PageBreak, LevelFormat
} = require("docx");

const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 60, bottom: 60, left: 100, right: 100 };
const headerShading = { fill: "2B579A", type: ShadingType.CLEAR };
const headerRun = (text) => new TextRun({ text, bold: true, color: "FFFFFF", font: "Arial", size: 20 });
const cellRun = (text, opts = {}) => new TextRun({ text, font: "Arial", size: 18, ...opts });
const boldRun = (text, opts = {}) => new TextRun({ text, font: "Arial", size: 18, bold: true, ...opts });

function makeTable(headers, rows, colWidths) {
  const totalWidth = colWidths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: totalWidth, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [
      new TableRow({
        children: headers.map((h, i) =>
          new TableCell({
            borders, shading: headerShading,
            width: { size: colWidths[i], type: WidthType.DXA },
            margins: cellMargins,
            children: [new Paragraph({ children: [headerRun(h)] })]
          })
        )
      }),
      ...rows.map(row =>
        new TableRow({
          children: row.map((cell, i) =>
            new TableCell({
              borders,
              width: { size: colWidths[i], type: WidthType.DXA },
              margins: cellMargins,
              children: [new Paragraph({ spacing: { before: 40, after: 40 }, children: parseBold(cell) })]
            })
          )
        })
      )
    ]
  });
}

// Parse **bold** in text
function parseBold(text) {
  const parts = [];
  const regex = /\*\*(.*?)\*\*/g;
  let last = 0;
  let m;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) parts.push(cellRun(text.slice(last, m.index)));
    parts.push(boldRun(m[1]));
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(cellRun(text.slice(last)));
  return parts;
}

function codeBlock(lines, lang = "") {
  return lines.map(line =>
    new Paragraph({
      shading: { fill: "F5F5F5", type: ShadingType.CLEAR },
      spacing: { before: 0, after: 0 },
      children: [new TextRun({ text: line || " ", font: "Courier New", size: 16, color: "333333" })]
    })
  );
}

function p(text, opts = {}) {
  return new Paragraph({
    spacing: { before: 120, after: 120 },
    ...opts,
    children: parseBoldParagraph(text)
  });
}

function parseBoldParagraph(text) {
  const parts = [];
  const regex = /\*\*(.*?)\*\*/g;
  let last = 0;
  let m;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) parts.push(new TextRun({ text: text.slice(last, m.index), font: "Arial", size: 22 }));
    parts.push(new TextRun({ text: m[1], font: "Arial", size: 22, bold: true }));
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(new TextRun({ text: text.slice(last), font: "Arial", size: 22 }));
  return parts;
}

function heading(text, level) {
  const sizes = { 1: 36, 2: 30, 3: 26 };
  const headingLevel = level === 1 ? HeadingLevel.HEADING_1 : level === 2 ? HeadingLevel.HEADING_2 : HeadingLevel.HEADING_3;
  return new Paragraph({
    heading: headingLevel,
    spacing: { before: 240, after: 120 },
    children: [new TextRun({ text, font: "Arial", size: sizes[level] || 24, bold: true })]
  });
}

function quote(text) {
  return new Paragraph({
    indent: { left: 720 },
    spacing: { before: 120, after: 120 },
    border: { left: { style: BorderStyle.SINGLE, size: 6, color: "2B579A", space: 8 } },
    children: parseBoldParagraph(text)
  });
}

function bulletItem(text) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    spacing: { before: 60, after: 60 },
    children: parseBoldParagraph(text)
  });
}

const children = [];

// Title
children.push(new Paragraph({
  heading: HeadingLevel.TITLE,
  spacing: { after: 360 },
  alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "EKS ComfyUI \u63A8\u7406\u90E8\u7F72\u65B9\u6848 vs GCP Cloud Run \u65B9\u6848\u5BF9\u6BD4", font: "Arial", size: 40, bold: true, color: "2B579A" })]
}));

// Architecture overview
children.push(heading("\u67B6\u6784\u6982\u89C8", 2));
children.push(p("\u4EE5\u4E0B\u662F EKS ComfyUI \u63A8\u7406\u90E8\u7F72\u67B6\u6784\u793A\u610F\uFF1A"));

const archLines = [
  "Client --> ALB Ingress --> ComfyUI Service (ClusterIP)",
  "                              |",
  "                    ComfyUI Pod (GPU Node)",
  "                    +-- ComfyUI Server (GPU Inference)",
  "                    +-- CW Metrics Sidecar --> CloudWatch (QueuePending)",
  "                    +-- models mount (hostPath, NVMe direct I/O)",
  "                        /opt/dlami/nvme/comfyui-models",
  "",
  "DaemonSet Prewarm    Karpenter         KEDA ScaledObject",
  "(S3->NVMe Sync)      (Node Pool)       (Pod Autoscaler)",
  "     |               g5/g6e GPU        CloudWatch trigger",
  "     v                    v",
  "S3 Models Bucket    EC2 GPU Instances (NVMe SSD + SOCI Image)",
];
children.push(...codeBlock(archLines));
children.push(new Paragraph({ spacing: { after: 120 } }));

// Section 1
children.push(heading("\u4E00\u3001\u5F39\u6027\u6269\u7F29\u80FD\u529B\u5BF9\u6BD4", 2));

children.push(makeTable(
  ["\u7EF4\u5EA6", "EKS (KEDA + Karpenter)", "GCP Cloud Run"],
  [
    ["**Pod \u7EA7\u6269\u7F29**", "KEDA \u57FA\u4E8E CloudWatch QueuePending \u6307\u6807\uFF0CpollingInterval=30s\uFF0CscaleUp \u7A33\u5B9A\u7A97\u53E3 60s\uFF0C\u7CBE\u51C6\u5339\u914D\u961F\u5217\u6DF1\u5EA6", "\u57FA\u4E8E\u5E76\u53D1\u8BF7\u6C42\u6570/CPU \u5229\u7528\u7387\uFF0C\u65E0\u6CD5\u611F\u77E5\u63A8\u7406\u961F\u5217\u8BED\u4E49"],
    ["**Node \u7EA7\u6269\u7F29**", "Karpenter \u79D2\u7EA7\u611F\u77E5 Pending Pod\uFF0C\u81EA\u52A8\u9009\u62E9 g5/g6e \u6700\u4F18\u5B9E\u4F8B\u65CF\uFF0C\u652F\u6301 On-Demand/Spot \u6DF7\u5408", "\u7531\u5E73\u53F0\u6258\u7BA1\uFF0C\u65E0\u6CD5\u6307\u5B9A\u5B9E\u4F8B\u65CF\uFF0CGPU \u578B\u53F7\u9009\u62E9\u53D7\u9650"],
    ["**\u7F29\u5BB9\u7B56\u7565**", "cooldownPeriod=180s + scaleDown \u7A33\u5B9A\u7A97\u53E3 300s + Karpenter WhenEmpty \u7B56\u7565\uFF0C\u907F\u514D GPU \u8282\u70B9\u6296\u52A8", "\u56FA\u5B9A\u51B7\u5374\u671F\uFF0C\u65E0\u6CD5\u9488\u5BF9 GPU \u5DE5\u4F5C\u8D1F\u8F7D\u7CBE\u7EC6\u8C03\u4F18"],
    ["**\u6700\u5927\u5F39\u6027**", "maxReplicaCount=10\uFF08\u53EF\u6309\u9700\u8C03\u6574\u81F3\u6570\u767E\uFF09\uFF0CKarpenter \u8282\u70B9\u6570\u7406\u8BBA\u4E0A\u65E0\u4E0A\u9650", "\u53D7\u533A\u57DF GPU \u914D\u989D\u9650\u5236\uFF0C\u6700\u5927\u5B9E\u4F8B\u6570\u901A\u5E38\u8F83\u4F4E"],
    ["**\u591A\u7EA7\u6269\u7F29\u8054\u52A8**", "KEDA\uFF08Pod\uFF09\u2192 Karpenter\uFF08Node\uFF09\u4E24\u7EA7\u8054\u52A8\uFF0C\u89E3\u8026\u5E94\u7528\u6269\u7F29\u4E0E\u57FA\u7840\u8BBE\u65BD\u6269\u7F29", "\u5355\u4E00\u6258\u7BA1\u6269\u7F29\uFF0C\u9ED1\u76D2\u4E0D\u53EF\u8C03"]
  ],
  [1800, 4200, 3360]
));

children.push(p("\u6838\u5FC3\u4F18\u52BF: EKS \u65B9\u6848\u7684 KEDA + Karpenter \u4E24\u7EA7\u8054\u52A8\u63D0\u4F9B\u4E86**\u961F\u5217\u611F\u77E5\u7684\u8BED\u4E49\u7EA7\u6269\u7F29**\u80FD\u529B\u3002KEDA \u901A\u8FC7 Sidecar \u5B9E\u65F6\u91C7\u96C6 ComfyUI \u961F\u5217\u6DF1\u5EA6\u5E76\u53D1\u5E03\u5230 CloudWatch\uFF0C\u5B9E\u73B0\u201C\u6709\u4EFB\u52A1\u5C31\u6269\u3001\u7A7A\u95F2\u5C31\u7F29\u201D\u7684\u7CBE\u51C6\u5F39\u6027\uFF1BKarpenter \u5728\u79D2\u7EA7\u54CD\u5E94 Pending Pod \u5E76\u667A\u80FD\u9009\u62E9\u6700\u4F18 GPU \u5B9E\u4F8B\uFF0C\u6574\u4F53\u4ECE\u8BF7\u6C42\u5230 GPU \u5C31\u7EEA\u7684\u7AEF\u5230\u7AEF\u6269\u5BB9\u53EF\u63A7\u5236\u5728 **2-3 \u5206\u949F**\u5185\u3002"));

// Implementation steps for section 1
children.push(heading("\u5B9E\u65BD\u6B65\u9AA4", 3));

children.push(p("**Step 1: \u5B89\u88C5 KEDA Operator \u5E76\u914D\u7F6E IRSA \u6743\u9650**"));
children.push(...codeBlock([
  "# \u5B89\u88C5 KEDA",
  "helm repo add kedacore https://kedacore.github.io/charts",
  "helm install keda kedacore/keda --namespace keda --create-namespace",
  "",
  "# \u4E3A KEDA Operator ServiceAccount \u7ED1\u5B9A CloudWatch \u8BFB\u53D6\u6743\u9650",
  "kubectl apply -f deploy/k8s-manifests/keda-operator-serviceaccount-irsa.yaml"
]));

children.push(p("KEDA Operator SA \u9700\u8981\u7684 IAM Role \u9700\u5305\u542B cloudwatch:GetMetricData \u6743\u9650\uFF1A"));
children.push(...codeBlock([
  "# keda-operator-serviceaccount-irsa.yaml",
  "apiVersion: v1",
  "kind: ServiceAccount",
  "metadata:",
  "  name: keda-operator",
  "  namespace: keda",
  "  annotations:",
  "    eks.amazonaws.com/role-arn: arn:aws:iam::${AWS_ACCOUNT_ID}:role/ComfyUICloudWatchRole"
]));

children.push(p("**Step 2: \u90E8\u7F72 TriggerAuthentication \u548C ScaledObject**"));
children.push(...codeBlock([
  "kubectl apply -f deploy/k8s-manifests/comfyui-keda-triggerauth.yaml",
  "kubectl apply -f deploy/k8s-manifests/comfyui-keda-scaledobject.yaml"
]));

children.push(p("ScaledObject \u6838\u5FC3\u914D\u7F6E\u2014\u2014\u57FA\u4E8E CloudWatch QueuePending \u6307\u6807\u505A\u961F\u5217\u611F\u77E5\u6269\u7F29\uFF1A"));
children.push(...codeBlock([
  "# comfyui-keda-scaledobject.yaml (\u5173\u952E\u5B57\u6BB5)",
  "spec:",
  "  scaleTargetRef:",
  "    name: comfyui",
  "  minReplicaCount: 1",
  "  maxReplicaCount: 10",
  "  cooldownPeriod: 180",
  "  pollingInterval: 30",
  "  triggers:",
  "  - type: aws-cloudwatch",
  "    metadata:",
  "      namespace: \"ComfyUI\"",
  "      metricName: \"QueuePending\"",
  "      targetMetricValue: \"1\"       # \u6BCF Pod 1 \u4E2A\u5F85\u5904\u7406\u4EFB\u52A1",
  "      metricStatPeriod: \"30\"",
  "    authenticationRef:",
  "      name: comfyui-cw-auth"
]));

children.push(p("**Step 3: \u90E8\u7F72 Karpenter GPU NodePool**"));
children.push(...codeBlock([
  "export CLUSTER_NAME=<your-cluster> AMI_ID=<dlami-id> SUBNET_ID_1=<subnet> SUBNET_ID_2=<subnet> SG_ID_1=<sg> SG_ID_2=<sg>",
  "envsubst < deploy/k8s-manifests/karpenter-ec2nodeclass-gpu.yaml | kubectl apply -f -",
  "kubectl apply -f deploy/k8s-manifests/karpenter-nodepool-gpu.yaml"
]));

children.push(p("NodePool \u6307\u5B9A g5/g6e \u5B9E\u4F8B\u65CF\uFF0C\u8282\u70B9\u81EA\u52A8\u6807\u8BB0 workload=gpu\uFF1A"));
children.push(...codeBlock([
  "# karpenter-nodepool-gpu.yaml (\u5173\u952E\u5B57\u6BB5)",
  "spec:",
  "  template:",
  "    metadata:",
  "      labels:",
  "        workload: \"gpu\"",
  "    spec:",
  "      requirements:",
  "      - key: karpenter.k8s.aws/instance-family",
  "        operator: In",
  "        values: [\"g5\", \"g6e\"]",
  "  disruption:",
  "    consolidationPolicy: WhenEmpty",
  "    consolidateAfter: 2m"
]));

children.push(p("**Step 4: \u9A8C\u8BC1\u4E24\u7EA7\u8054\u52A8**"));
children.push(...codeBlock([
  "# \u67E5\u770B KEDA ScaledObject \u72B6\u6001",
  "kubectl get scaledobject comfyui-cw-scaler -o wide",
  "",
  "# \u67E5\u770B HPA\uFF08KEDA \u81EA\u52A8\u521B\u5EFA\uFF09",
  "kubectl get hpa",
  "",
  "# \u89C2\u5BDF\u6269\u5BB9\u5168\u94FE\u8DEF",
  "kubectl get pods -l app=comfyui -w",
  "kubectl get nodes -l workload=gpu -w",
  "kubectl logs -l app=comfyui-nvme-prewarm -f"
]));

children.push(p("**HyperPod EKS \u9002\u914D**: \u5C06 Step 3 \u66FF\u6362\u4E3A HyperPod \u4E13\u5C5E\u8D44\u6E90\u5373\u53EF\uFF0CKEDA \u90E8\u5206\u65E0\u9700\u6539\u52A8\uFF1A"));
children.push(...codeBlock([
  "# HyperPod \u96C6\u7FA4\u4F7F\u7528 HyperpodNodeClass \u66FF\u4EE3 EC2NodeClass",
  "export HP_INSTANCE_GROUP_1=<your-instance-group>",
  "envsubst < deploy/k8s-manifests/karpenter-hyperpod-nodeclass-gpu.yaml | kubectl apply -f -",
  "kubectl apply -f deploy/k8s-manifests/karpenter-hyperpod-nodepool-gpu.yaml"
]));

children.push(quote("HyperPod \u96C6\u7FA4\u9700\u542F\u7528 NodeProvisioningMode=Continuous \u548C NodeRecovery=Automatic\u3002Karpenter \u901A\u8FC7 HyperpodNodeClass \u7BA1\u7406\u8282\u70B9\u751F\u547D\u5468\u671F\uFF0CGPU \u786C\u4EF6\u6545\u969C\u65F6\u81EA\u52A8\u66FF\u6362\u8282\u70B9\u3002"));

// Section 2
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(heading("\u4E8C\u3001\u6A21\u578B\u52A0\u8F7D\u4E0E\u5B58\u50A8\u6027\u80FD\u5BF9\u6BD4", 2));
children.push(heading("2.1 Lustre/S3 \u2192 NVMe \u9884\u70ED\u52A0\u901F", 3));

children.push(makeTable(
  ["\u7EF4\u5EA6", "EKS (DaemonSet + NVMe)", "GCP Cloud Run"],
  [
    ["**\u6A21\u578B\u5B58\u50A8\u5C42**", "S3 \u4F5C\u4E3A Source of Truth\uFF0CDaemonSet \u9884\u70ED\u540C\u6B65\u81F3\u8282\u70B9\u672C\u5730 NVMe SSD", "GCS \u901A\u8FC7 FUSE mount \u6302\u8F7D\uFF0C\u6BCF\u6B21\u51B7\u542F\u52A8\u9700\u8FDC\u7A0B\u62C9\u53D6"],
    ["**\u540C\u6B65\u673A\u5236**", "DaemonSet comfyui-nvme-prewarm \u5728 GPU \u8282\u70B9\u5C31\u7EEA\u540E\u7ACB\u5373 aws s3 sync \u5168\u91CF\u6A21\u578B\u81F3 NVMe", "\u65E0\u9884\u70ED\u673A\u5236\uFF0C\u4F9D\u8D56\u8FD0\u884C\u65F6\u6309\u9700\u62C9\u53D6"],
    ["**\u5B58\u50A8\u4ECB\u8D28**", "EC2 \u5B9E\u4F8B\u672C\u5730 NVMe SSD\uFF08g5: \u6700\u9AD8 3.8GB/s \u987A\u5E8F\u8BFB\u53D6\uFF09", "\u7F51\u7EDC\u6587\u4EF6\u7CFB\u7EDF\uFF08GCS FUSE\uFF0C\u53D7\u7F51\u7EDC\u5E26\u5BBD\u9650\u5236\uFF09"],
    ["**\u53EF\u6269\u5C55\u81F3 Lustre**", "\u53EF\u66FF\u6362 S3 \u4E3A FSx for Lustre\uFF08\u805A\u5408\u5E26\u5BBD TB/s \u7EA7\uFF09\uFF0C\u5927\u5E45\u52A0\u901F\u591A\u8282\u70B9\u5E76\u884C\u540C\u6B65", "\u65E0\u5BF9\u5E94\u9AD8\u6027\u80FD\u5E76\u884C\u6587\u4EF6\u7CFB\u7EDF"]
  ],
  [1800, 4200, 3360]
));

children.push(quote("Lustre \u52A0\u901F\u8DEF\u5F84: S3 Bucket \u2192 FSx for Lustre\uFF08\u81EA\u52A8\u5173\u8054 S3\uFF0C\u63D0\u4F9B 200MB/s/TiB \u57FA\u7EBF\u541E\u5410\uFF09\u2192 DaemonSet \u540C\u6B65\u81F3 NVMe\u3002\u5BF9\u4E8E 50GB+ \u6A21\u578B\u96C6\u5408\uFF0CLustre \u805A\u5408\u5E26\u5BBD\u76F8\u6BD4\u76F4\u63A5 S3 \u4E0B\u8F7D\u53EF\u63D0\u901F **3-5x**\u3002"));

children.push(heading("2.2 HostPath \u6302\u8F7D vs Cloud Run Mount \u6027\u80FD", 3));

children.push(makeTable(
  ["\u7EF4\u5EA6", "EKS hostPath (NVMe)", "Cloud Run Volume Mount"],
  [
    ["**\u6302\u8F7D\u65B9\u5F0F**", "hostPath \u76F4\u63A5\u6620\u5C04\u5BBF\u4E3B\u673A NVMe \u8DEF\u5F84\uFF0C\u96F6\u62BD\u8C61\u5C42\u5F00\u9500", "GCS FUSE mount \u6216 NFS\uFF0C\u7ECF\u8FC7\u7528\u6237\u6001\u6587\u4EF6\u7CFB\u7EDF\u5C42"],
    ["**I/O \u5EF6\u8FDF**", "**\u5FAE\u79D2\u7EA7** \u2014 \u672C\u5730 NVMe \u5757\u8BBE\u5907\u76F4\u8FDE\uFF0C\u65E0\u7F51\u7EDC\u5F80\u8FD4", "**\u6BEB\u79D2\u7EA7** \u2014 \u6BCF\u6B21 read \u9700\u7F51\u7EDC\u5F80\u8FD4\u6216 FUSE \u7F13\u5B58\u67E5\u627E"],
    ["**\u968F\u673A\u8BFB\u6027\u80FD**", "NVMe 4K \u968F\u673A\u8BFB ~500K IOPS\uFF0C\u6A21\u578B\u6743\u91CD\u52A0\u8F7D\u8FD1\u4E4E\u77AC\u65F6", "FUSE \u968F\u673A\u8BFB\u53D7\u9650\u4E8E\u7F51\u7EDC RTT\uFF0C\u5927\u6A21\u578B\u52A0\u8F7D\u8017\u65F6\u663E\u8457"],
    ["**\u63A8\u7406\u70ED\u8DEF\u5F84**", "\u6A21\u578B\u6743\u91CD\u5E38\u9A7B\u5185\u5B58\u540E\uFF0CLoRA \u70ED\u5207\u6362\u4ECE NVMe \u8BFB\u53D6\uFF0C\u5EF6\u8FDF < 1s", "LoRA/checkpoint \u5207\u6362\u9700\u91CD\u65B0\u62C9\u53D6\uFF0C\u5EF6\u8FDF\u6570\u79D2\u81F3\u6570\u5341\u79D2"]
  ],
  [1800, 4200, 3360]
));

children.push(p("**\u5173\u952E\u5DEE\u5F02**: ComfyUI \u63A8\u7406\u6D89\u53CA\u9891\u7E41\u7684\u6A21\u578B\u6743\u91CD\u52A0\u8F7D\uFF08diffusion model\u3001VAE\u3001CLIP\u3001LoRA\uFF09\uFF0CEKS \u65B9\u6848\u4E2D\u6A21\u578B\u5DF2\u9884\u70ED\u81F3 NVMe \u540E\u901A\u8FC7 hostPath \u6302\u8F7D\uFF0C**\u8BFB\u53D6\u5EF6\u8FDF\u6BD4 Cloud Run \u7684 FUSE mount \u4F4E 2-3 \u4E2A\u6570\u91CF\u7EA7**\uFF0C\u76F4\u63A5\u5F71\u54CD\u9996\u6B21\u63A8\u7406\u5EF6\u8FDF\u548C\u6A21\u578B\u5207\u6362\u901F\u5EA6\u3002"));

// Section 2 implementation steps
children.push(heading("\u5B9E\u65BD\u6B65\u9AA4", 3));
children.push(p("**Step 1: \u4E0A\u4F20\u6A21\u578B\u81F3 S3\uFF08Source of Truth\uFF09**"));
children.push(...codeBlock([
  "aws s3 sync ./models s3://comfyui-models-bucket-${AWS_ACCOUNT_ID}/models/ --region us-west-2"
]));

children.push(p("**Step 2: \u90E8\u7F72 NVMe \u9884\u70ED DaemonSet**"));
children.push(...codeBlock([
  "kubectl apply -f deploy/k8s-manifests/comfyui-nvme-prewarm-daemonset.yaml"
]));
children.push(p("DaemonSet \u901A\u8FC7 nodeSelector: workload: gpu \u786E\u4FDD\u4EC5\u5728 GPU \u8282\u70B9\u4E0A\u8FD0\u884C\uFF1A"));
children.push(...codeBlock([
  "# comfyui-nvme-prewarm-daemonset.yaml (\u5173\u952E\u5B57\u6BB5)",
  "spec:",
  "  template:",
  "    spec:",
  "      serviceAccountName: comfyui-prewarm-sa",
  "      nodeSelector:",
  "        workload: gpu",
  "      containers:",
  "      - name: prewarm",
  "        args:",
  "        - |",
  "          aws s3 sync \"s3://comfyui-models-bucket-${AWS_ACCOUNT_ID}/models/\"",
  "                      \"/opt/dlami/nvme/comfyui-models/\"",
  "          sleep infinity",
  "        volumeMounts:",
  "        - name: nvme-host",
  "          mountPath: /opt/dlami/nvme/comfyui-models",
  "      volumes:",
  "      - name: nvme-host",
  "        hostPath:",
  "          path: /opt/dlami/nvme/comfyui-models",
  "          type: DirectoryOrCreate"
]));

children.push(p("**Step 3: ComfyUI Deployment \u4E2D\u914D\u7F6E hostPath \u6302\u8F7D**"));
children.push(...codeBlock([
  "# comfyui-deployment.yaml (\u5173\u952E\u5B57\u6BB5)",
  "spec:",
  "  template:",
  "    spec:",
  "      containers:",
  "      - name: comfyui",
  "        volumeMounts:",
  "        - name: nvme-host",
  "          mountPath: /opt/program/models",
  "          readOnly: true",
  "        readinessProbe:",
  "          httpGet:",
  "            path: /",
  "            port: 8188",
  "          initialDelaySeconds: 60",
  "          periodSeconds: 10",
  "      volumes:",
  "      - name: nvme-host",
  "        hostPath:",
  "          path: /opt/dlami/nvme/comfyui-models",
  "          type: DirectoryOrCreate"
]));

children.push(p("**Step 4: \u9A8C\u8BC1\u6A21\u578B\u9884\u70ED\u548C\u6302\u8F7D**"));
children.push(...codeBlock([
  "kubectl get ds comfyui-nvme-prewarm -o wide",
  "kubectl logs -l app=comfyui-nvme-prewarm --tail=20",
  "kubectl exec -it deploy/comfyui -c comfyui -- ls -lh /opt/program/models/"
]));

children.push(p("**HyperPod EKS \u9002\u914D**: HyperPod \u7BA1\u7406\u7684 GPU \u8282\u70B9\u9ED8\u8BA4\u914D\u5907\u672C\u5730 NVMe SSD\uFF0CDaemonSet \u548C hostPath \u6302\u8F7D\u8DEF\u5F84\u4E0E\u6807\u51C6 EKS \u5B8C\u5168\u4E00\u81F4\uFF0C\u65E0\u9700\u4EFB\u4F55\u6539\u52A8\u3002"));

// Section 3
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(heading("\u4E09\u3001\u63A8\u7406\u63D0\u901F\u5168\u94FE\u8DEF\u4F18\u5316\u624B\u6BB5", 2));

children.push(p("EKS \u65B9\u6848\u5728\u6A21\u578B\u63A8\u7406\u7684\u5168\u751F\u547D\u5468\u671F\u4E2D\u63D0\u4F9B\u4E86\u591A\u5C42\u6B21\u63D0\u901F\u624B\u6BB5\uFF1A"));

children.push(makeTable(
  ["\u4F18\u5316\u624B\u6BB5", "EKS \u5B9E\u73B0\u65B9\u5F0F", "Cloud Run \u53EF\u884C\u6027"],
  [
    ["**SOCI \u955C\u50CF Lazy Loading**", "ECR + SOCI Index\uFF0C\u955C\u50CF\u5C31\u7EEA\u65F6\u95F4\u4ECE\u5206\u949F\u7EA7\u964D\u81F3 **10-20 \u79D2**", "\u4E0D\u652F\u6301\uFF0C\u4F9D\u8D56 Artifact Registry \u5168\u91CF\u62C9\u53D6"],
    ["**DaemonSet \u6A21\u578B\u9884\u70ED**", "GPU \u8282\u70B9\u5C31\u7EEA\u5373\u89E6\u53D1 S3\u2192NVMe \u5168\u91CF\u540C\u6B65", "\u65E0 DaemonSet \u6982\u5FF5\uFF0C\u65E0\u6CD5\u5B9E\u73B0\u8282\u70B9\u7EA7\u9884\u70ED"],
    ["**GPU \u9A71\u52A8\u9884\u52A0\u8F7D**", "NVIDIA DLAMI \u9884\u88C5 CUDA/cuDNN/\u9A71\u52A8", "\u5E73\u53F0\u7BA1\u7406\uFF0C\u9A71\u52A8\u7248\u672C\u4E0D\u53EF\u63A7"],
    ["**CUDA Graph / TorchCompile \u7F13\u5B58**", "\u7F16\u8BD1\u4EA7\u7269\u7F13\u5B58\u81F3 NVMe\uFF0C\u540E\u7EED Pod \u53EF\u590D\u7528", "\u6BCF\u6B21\u51B7\u542F\u52A8\u91CD\u65B0\u7F16\u8BD1\uFF0C\u65E0\u6301\u4E45\u5316\u7F13\u5B58"],
    ["**\u6A21\u578B\u6743\u91CD\u5185\u5B58\u9884\u52A0\u8F7D**", "\u901A\u8FC7 readinessProbe \u786E\u4FDD\u6A21\u578B\u52A0\u8F7D\u5B8C\u6BD5\u624D\u63A5\u6D41\u91CF", "\u652F\u6301\u4F46\u7C92\u5EA6\u7C97\uFF0C\u65E0\u6CD5\u914D\u5408\u9884\u70ED\u903B\u8F91"],
    ["**Session Affinity**", "ClientIP \u4EB2\u548C\uFF083h TTL\uFF09\uFF0C\u547D\u4E2D\u5DF2\u52A0\u8F7D\u6A21\u578B/LoRA", "\u652F\u6301\u4F46\u53D7\u5E73\u53F0\u7F29\u5BB9\u7B56\u7565\u5F71\u54CD\uFF0C\u4EB2\u548C\u6027\u4E0D\u7A33\u5B9A"],
    ["**NVMe tmpfs \u52A0\u901F**", "\u63A8\u7406\u4E2D\u95F4\u4EA7\u7269\u5199\u5165 NVMe ephemeral storage\uFF0860Gi\uFF09", "ephemeral storage \u53D7\u9650\u4E14\u4E0D\u53EF\u6307\u5B9A\u4ECB\u8D28"]
  ],
  [2200, 3800, 3360]
));

// Section 3 implementation steps
children.push(heading("\u5B9E\u65BD\u6B65\u9AA4", 3));
children.push(p("**Step 1: \u6784\u5EFA SOCI \u7D22\u5F15\u52A0\u901F\u955C\u50CF\u62C9\u53D6**"));
children.push(...codeBlock([
  "# \u63A8\u9001 ComfyUI \u955C\u50CF\u81F3 ECR",
  "docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/comfyui-s3:latest",
  "",
  "# \u4E3A\u955C\u50CF\u521B\u5EFA SOCI Index",
  "soci create ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/comfyui-s3:latest",
  "soci push --ref ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/comfyui-s3:latest"
]));

children.push(p("\u8282\u70B9\u4FA7 SOCI \u914D\u7F6E\uFF08HyperPod \u751F\u547D\u5468\u671F\u811A\u672C\uFF09\u2014\u2014 containerd \u914D\u7F6E\uFF1A"));
children.push(...codeBlock([
  "# /opt/sagemaker/containerd/config.toml",
  "[plugins.\"io.containerd.grpc.v1.cri\".containerd]",
  "default_runtime_name = \"nvidia\"",
  "snapshotter = \"soci\"",
  "discard_unpacked_layers = true",
  "disable_snapshot_annotations = false",
  "",
  "[proxy_plugins.soci]",
  "type = \"snapshot\"",
  "address = \"/run/soci-snapshotter-grpc/soci-snapshotter-grpc.sock\"",
  "",
  "[proxy_plugins.soci.exports]",
  "root = \"/opt/dlami/nvme/soci-snapshotter-grpc\""
]));

children.push(p("SOCI snapshotter \u914D\u7F6E\uFF1A"));
children.push(...codeBlock([
  "# /etc/soci-snapshotter-grpc/config.toml",
  "[content_store]",
  "  type = \"containerd\"",
  "",
  "[pull_modes.parallel_pull_unpack]",
  "  enable = true",
  "  max_concurrent_downloads = 50",
  "  max_concurrent_downloads_per_image = 10",
  "  concurrent_download_chunk_size = \"8mb\"",
  "  max_concurrent_unpacks = 20"
]));

children.push(p("**Step 2: \u90E8\u7F72 CloudWatch Metrics Sidecar**"));
children.push(...codeBlock([
  "# comfyui-deployment.yaml \u4E2D\u7684 Sidecar \u5BB9\u5668",
  "- name: comfyui-cw-metrics",
  "  image: ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/comfyui-queue-metrics:latest",
  "  env:",
  "  - name: COMFYUI_QUEUE_URL",
  "    value: \"http://127.0.0.1:8188/queue\"",
  "  - name: METRIC_NAMESPACE",
  "    value: \"ComfyUI\"",
  "  - name: METRIC_NAME",
  "    value: \"QueuePending\"",
  "  - name: POLL_INTERVAL_SEC",
  "    value: \"10\"",
  "  resources:",
  "    requests:",
  "      cpu: 50m",
  "      memory: 64Mi"
]));

children.push(p("**Step 3: \u90E8\u7F72 ComfyUI Service\uFF08Session Affinity + Readiness\uFF09**"));
children.push(...codeBlock([
  "kubectl apply -f deploy/k8s-manifests/comfyui-deployment.yaml",
  "kubectl apply -f deploy/k8s-manifests/comfyui-service.yaml"
]));

children.push(p("Service \u914D\u7F6E ClientIP \u4EB2\u548C\uFF1A"));
children.push(...codeBlock([
  "# comfyui-service.yaml",
  "spec:",
  "  sessionAffinity: ClientIP",
  "  sessionAffinityConfig:",
  "    clientIP:",
  "      timeoutSeconds: 10800    # 3 \u5C0F\u65F6\u4EB2\u548C\u7A97\u53E3"
]));

children.push(p("**Step 4: \u9A8C\u8BC1\u5168\u94FE\u8DEF\u4F18\u5316\u6548\u679C**"));
children.push(...codeBlock([
  "# \u786E\u8BA4 SOCI Lazy Loading \u751F\u6548",
  "kubectl describe pod -l app=comfyui | grep -A5 \"Events\"",
  "",
  "# \u67E5\u770B CloudWatch \u6307\u6807",
  "aws cloudwatch get-metric-statistics \\",
  "  --namespace ComfyUI --metric-name QueuePending \\",
  "  --period 30 --statistics Average"
]));

// Section 4
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(heading("\u56DB\u3001\u7EFC\u5408\u5BF9\u6BD4\u603B\u7ED3", 2));

children.push(makeTable(
  ["\u8BC4\u4F30\u7EF4\u5EA6", "EKS \u65B9\u6848", "Cloud Run \u65B9\u6848"],
  [
    ["**\u51B7\u542F\u52A8\u7AEF\u5230\u7AEF**", "SOCI(~15s) + NVMe\u9884\u70ED\u6A21\u578B(\u5DF2\u5C31\u4F4D) + \u6A21\u578B\u52A0\u8F7D(~45s) \u2248 **~60-90s**", "\u955C\u50CF\u62C9\u53D6(~120s) + FUSE\u6A21\u578B\u52A0\u8F7D(~60-180s) \u2248 **3-5min**"],
    ["**\u6A21\u578B\u5207\u6362\u5EF6\u8FDF**", "NVMe hostPath \u76F4\u8BFB < **1s**", "GCS FUSE \u8FDC\u7A0B\u62C9\u53D6 **10-30s**"],
    ["**\u6269\u7F29\u7CBE\u5EA6**", "\u961F\u5217\u8BED\u4E49\u611F\u77E5\uFF0CPod/Node \u4E24\u7EA7\u8054\u52A8", "\u5E76\u53D1/CPU \u6307\u6807\uFF0C\u5355\u7EA7\u9ED1\u76D2"],
    ["**GPU \u5B9E\u4F8B\u9009\u62E9**", "Karpenter \u652F\u6301 g5/g6e/p4d \u7B49\u4EFB\u610F\u65CF", "\u53D7\u9650\u4E8E Cloud Run GPU \u53EF\u7528\u578B\u53F7 (L4/A100)"],
    ["**\u6210\u672C\u4F18\u5316**", "Spot \u5B9E\u4F8B + WhenEmpty \u7F29\u5BB9 + \u7CBE\u51C6\u6269\u7F29\u907F\u514D\u8FC7\u5EA6\u914D\u7F6E", "\u6309\u8BF7\u6C42\u8BA1\u8D39\uFF0CGPU \u95F2\u7F6E\u4ECD\u6536\u8D39"],
    ["**\u751F\u6001\u96C6\u6210**", "CloudWatch + IRSA/Pod Identity + ALB + WAF \u5168\u6808", "GCP \u751F\u6001\u95ED\u73AF\uFF0C\u8DE8\u4E91\u80FD\u529B\u5F31"],
    ["**\u8FD0\u7EF4\u590D\u6742\u5EA6**", "\u4E2D\u7B49\uFF08\u9700\u7BA1\u7406 KEDA/Karpenter/DaemonSet\uFF09", "\u4F4E\uFF08\u5168\u6258\u7BA1\uFF09"]
  ],
  [2000, 3800, 3560]
));

children.push(p("**\u7ED3\u8BBA**: EKS \u65B9\u6848\u901A\u8FC7 KEDA \u961F\u5217\u611F\u77E5\u6269\u7F29 + Karpenter \u667A\u80FD\u8282\u70B9\u4F9B\u7ED9 + SOCI \u955C\u50CF\u61D2\u52A0\u8F7D + DaemonSet NVMe \u9884\u70ED + hostPath \u96F6\u5F00\u9500\u6302\u8F7D\u7684\u5168\u94FE\u8DEF\u4F18\u5316\u7EC4\u5408\uFF0C\u5728 GPU \u63A8\u7406\u573A\u666F\u4E0B\u5B9E\u73B0\u4E86**\u51B7\u542F\u52A8\u65F6\u95F4\u964D\u4F4E 3-4x\u3001\u6A21\u578B\u5207\u6362\u5EF6\u8FDF\u964D\u4F4E 10-30x\u3001\u6269\u7F29\u7CBE\u5EA6\u548C\u6210\u672C\u6548\u7387\u663E\u8457\u4F18\u4E8E Cloud Run** \u7684\u7EFC\u5408\u4F18\u52BF\u3002\u5BF9\u4E8E\u9AD8\u541E\u5410\u3001\u4F4E\u5EF6\u8FDF\u3001\u591A\u6A21\u578B\u5207\u6362\u9891\u7E41\u7684 ComfyUI \u63A8\u7406\u5DE5\u4F5C\u8D1F\u8F7D\uFF0CEKS \u65B9\u6848\u662F\u66F4\u4F18\u7684\u751F\u4EA7\u7EA7\u9009\u62E9\u3002"));

// HyperPod summary
children.push(heading("HyperPod EKS \u90E8\u7F72\u53EF\u884C\u6027\u603B\u7ED3", 3));
children.push(p("\u5728 AWS HyperPod EKS \u96C6\u7FA4\u4E0A\u90E8\u7F72\u672C\u65B9\u6848\u6574\u4F53**\u53EF\u884C\u4E14\u63A8\u8350**\uFF0C\u4E0E\u6807\u51C6 EKS \u7684\u5DEE\u5F02\u4EC5\u5728 Karpenter \u8282\u70B9\u7BA1\u7406\u5C42\uFF0C\u5176\u4F59\u7EC4\u4EF6\u5F00\u7BB1\u5373\u7528\u3002"));

children.push(p("**\u6807\u51C6 EKS \u2192 HyperPod EKS \u9002\u914D\u6E05\u5355\uFF1A**"));

children.push(makeTable(
  ["\u7EC4\u4EF6", "\u6807\u51C6 EKS", "HyperPod EKS", "\u9700\u6539\u52A8"],
  [
    ["Karpenter NodeClass", "EC2NodeClass", "HyperpodNodeClass", "**\u662F**"],
    ["Karpenter NodePool", "nodeClassRef.kind: EC2NodeClass", "nodeClassRef.kind: HyperpodNodeClass", "**\u662F**"],
    ["SOCI \u914D\u7F6E", "AMI \u9884\u88C5\u6216 userData \u811A\u672C", "on_create \u751F\u547D\u5468\u671F\u811A\u672C\u81EA\u52A8\u914D\u7F6E", "\u5426\uFF08\u5DF2\u5185\u7F6E\uFF09"],
    ["KEDA ScaledObject", "\u65E0\u53D8\u5316", "\u65E0\u53D8\u5316", "\u5426"],
    ["DaemonSet \u9884\u70ED", "\u65E0\u53D8\u5316", "\u65E0\u53D8\u5316", "\u5426"],
    ["ComfyUI Deployment", "\u65E0\u53D8\u5316", "\u65E0\u53D8\u5316", "\u5426"],
    ["Service / Ingress", "\u65E0\u53D8\u5316", "\u65E0\u53D8\u5316", "\u5426"]
  ],
  [2200, 2600, 2800, 1760]
));

children.push(p("**HyperPod \u4E13\u5C5E\u90E8\u7F72\u547D\u4EE4\uFF1A**"));
children.push(...codeBlock([
  "# \u66FF\u6362\u6807\u51C6 EKS \u7684 EC2NodeClass + NodePool",
  "export HP_INSTANCE_GROUP_1=<your-hyperpod-instance-group>",
  "envsubst < deploy/k8s-manifests/karpenter-hyperpod-nodeclass-gpu.yaml | kubectl apply -f -",
  "kubectl apply -f deploy/k8s-manifests/karpenter-hyperpod-nodepool-gpu.yaml",
  "",
  "# \u5176\u4F59\u7EC4\u4EF6\u4E0E\u6807\u51C6 EKS \u5B8C\u5168\u4E00\u81F4",
  "kubectl apply -f deploy/k8s-manifests/comfyui-nvme-prewarm-daemonset.yaml",
  "kubectl apply -f deploy/k8s-manifests/comfyui-keda-triggerauth.yaml",
  "kubectl apply -f deploy/k8s-manifests/comfyui-keda-scaledobject.yaml",
  "kubectl apply -f deploy/k8s-manifests/comfyui-deployment.yaml",
  "kubectl apply -f deploy/k8s-manifests/comfyui-service.yaml"
]));

children.push(p("**HyperPod \u72EC\u6709\u4F18\u52BF\uFF1A**"));
children.push(bulletItem("**\u8282\u70B9\u6545\u969C\u81EA\u6108**: NodeRecovery=Automatic\uFF0CGPU \u786C\u4EF6\u6545\u969C\u65F6\u81EA\u52A8\u66FF\u6362\u8282\u70B9\uFF0C\u65E0\u9700\u4EBA\u5DE5\u5E72\u9884"));
children.push(bulletItem("**NVMe \u5B58\u50A8**: HyperPod GPU \u5B9E\u4F8B\uFF08g5/g6e/p4d\uFF09\u5747\u914D\u5907\u672C\u5730 NVMe SSD\uFF0CDaemonSet \u9884\u70ED\u8DEF\u5F84\u4E00\u81F4"));
children.push(bulletItem("**SOCI Lazy Loading**: \u5DF2\u901A\u8FC7 on_create_eks_v3.sh \u751F\u547D\u5468\u671F\u811A\u672C\u81EA\u52A8\u914D\u7F6E\uFF0C\u65B0\u8282\u70B9\u5F00\u7BB1\u5373\u7528"));

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Arial", color: "2B579A" },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: "Arial", color: "2B579A" },
        paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Arial", color: "333333" },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 } },
    ]
  },
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] }
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1260, bottom: 1440, left: 1260 }
      }
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [new TextRun({ text: "EKS ComfyUI vs Cloud Run \u5BF9\u6BD4", font: "Arial", size: 18, color: "999999", italics: true })]
        })]
      })
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "Page ", font: "Arial", size: 18, color: "999999" }), new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 18, color: "999999" })]
        })]
      })
    },
    children
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("/Users/tangqy/workspaces/open-gallery/docs/eks-vs-cloudrun-comparison.docx", buffer);
  console.log("DOCX created successfully!");
});
