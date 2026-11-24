import { defineConfig } from 'vitepress'

export default defineConfig({
  lang: 'zh-CN',
  title: 'EONSim Research & Learning',
  description: 'High-performance multiphysics computing: mathematics, numerical methods, software engineering, HPC and EONSim development.',
  cleanUrls: true,
  srcExclude: ['drafts/**', 'templates/**'],
  markdown: {
    math: {
      tex: { tags: 'ams', inlineMath: [['$', '$'], ['\\(', '\\)']], displayMath: [['$$', '$$'], ['\\[', '\\]']] }
    }
  },
  themeConfig: {
    siteTitle: 'EONSim Research & Learning',
    nav: [
      { text: '首页', link: '/' },
      { text: '学习路径', link: '/learning/' },
      { text: '知识专题', link: '/knowledge/' },
      { text: '教程', link: '/tutorials/' },
      { text: '研发记录', link: '/development/' },
      { text: 'GitHub', link: 'https://github.com/saitoasukakawaii/EONSim-new' }
    ],
    sidebar: {
      '/learning/': [{ text: '学习路径', items: [
        { text: '总览', link: '/learning/' },
        { text: 'CFD 求解器', link: '/learning/cfd' },
        { text: '有限元与固体力学', link: '/learning/fem' },
        { text: 'HPC 与并行计算', link: '/learning/hpc' },
        { text: 'HPC 开源软件阅读指南', link: '/learning/open-source-hpc' }
      ]}],
      '/knowledge/': [{ text: '知识专题', items: [
        { text: '专题总览', link: '/knowledge/' },
        { text: '并行稀疏矩阵装配', link: '/knowledge/parallel-sparse-assembly' },
        { text: '单体 FSI 架构', link: '/knowledge/monolithic-fsi' },
        { text: '振荡圆管的流量与压力', link: '/knowledge/womersley-verification' },
        { text: '移动域的质量预算', link: '/knowledge/ale-mass-budget' },
        { text: '四面体黏性积分', link: '/knowledge/tet4-viscosity' }
      ]}],
      '/tutorials/': [{ text: '实践教程', items: [
        { text: '教程总览', link: '/tutorials/' },
        { text: '构建与运行 EONSim', link: '/tutorials/build-and-run' },
        { text: 'P2 三角形验证', link: '/tutorials/p2-verification' }
      ]}],
      '/development/': [{ text: '项目研发', items: [
        { text: '研发总览', link: '/development/' },
        { text: '开发与知识发布规范', link: '/development/contribution' }
      ]}]
    },
    search: { provider: 'local' },
    socialLinks: [{ icon: 'github', link: 'https://github.com/saitoasukakawaii/EONSim-new' }],
    footer: { message: 'Research, implementation and verification should remain traceable.', copyright: 'Copyright © EONSim contributors' },
    editLink: { pattern: 'https://github.com/saitoasukakawaii/EONSim-new/edit/main/website/:path', text: '在 GitHub 上编辑此页' }
  }
})
